"""OctoAuthor CLI - entry point for all commands."""

import typer
from rich.console import Console

app = typer.Typer(
    name="octoauthor",
    help="AI-powered user documentation generator with zero-trust security.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def version() -> None:
    """Show OctoAuthor version."""
    from octoauthor import __version__

    console.print(f"OctoAuthor v{__version__}")


@app.command()
def serve(
    server: str = typer.Argument(help="MCP server to run (e.g., 'doc-store-server')"),
    port: int = typer.Option(0, help="Port to listen on (0 = use default)"),
    host: str = typer.Option("127.0.0.1", help="Host to bind to"),
) -> None:
    """Run a specific MCP server for development."""
    from octoauthor.mcp_servers.registry import create_server, get_default_port, list_servers

    if server == "list":
        from octoauthor.core.config import get_settings

        settings = get_settings()
        console.print("[bold]Available MCP servers:[/bold]")
        for name in list_servers():
            configured_port = get_default_port(name)
            console.print(f"  {name}  (port: {configured_port})")
        console.print(f"  api  (port: {settings.api_port})")
        console.print("\n[dim]Ports are configured via .env (OCTOAUTHOR_ prefix)[/dim]")
        return

    if server == "api":
        import uvicorn

        from octoauthor.core.config import get_settings
        from octoauthor.service import create_app

        settings = get_settings()
        effective_port = port if port > 0 else settings.api_port
        console.print(f"Starting [bold]discovery API[/bold] on {host}:{effective_port}...")
        uvicorn.run(create_app(), host=host, port=effective_port, log_level="info")
        return

    try:
        mcp_server = create_server(server)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None

    effective_port = port if port > 0 else get_default_port(server)
    console.print(f"Starting [bold]{server}[/bold] on {host}:{effective_port}...")
    mcp_server.settings.host = host
    mcp_server.settings.port = effective_port
    mcp_server.run(transport="sse")


@app.command()
def run(
    config: str = typer.Option("config.yaml", help="Path to capture config file"),
    target: str = typer.Option(..., help="Base URL of the running target application"),
    dry_run: bool = typer.Option(False, help="Preview what would be generated without writing"),
) -> None:
    """Run the full documentation generation pipeline."""
    import asyncio

    from octoauthor.pipeline import run_pipeline

    console.print(f"Running OctoAuthor pipeline against [bold]{target}[/bold]...")
    console.print(f"Config: {config}")
    if dry_run:
        console.print("[yellow]DRY RUN - no files will be written[/yellow]")

    try:
        asyncio.run(run_pipeline(config_path=config, target_url=target, dry_run=dry_run))
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None
    except Exception as e:
        console.print(f"[red]Pipeline error:[/red] {e}")
        raise typer.Exit(1) from None


@app.command()
def audit(
    pr: int = typer.Option(..., help="GitHub PR number to audit"),
    repo: str = typer.Option(..., help="GitHub repo (owner/name)"),
    post_review: bool = typer.Option(False, help="Post review to GitHub PR"),
    skip_llm: bool = typer.Option(False, help="Skip LLM review (security scanners only)"),
) -> None:
    """Run the auditor agent against a PR."""
    import asyncio
    import os

    from rich.table import Table

    from octoauthor.auditor import run_audit
    from octoauthor.core.models.agents import AuditSeverity

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        console.print("[red]Error:[/red] GITHUB_TOKEN environment variable is required")
        raise typer.Exit(1)

    console.print(f"Auditing PR #{pr} on [bold]{repo}[/bold]...")

    try:
        report = asyncio.run(
            run_audit(repo, pr, token, post_review=post_review, skip_llm=skip_llm)
        )
    except Exception as e:
        console.print(f"[red]Audit error:[/red] {e}")
        raise typer.Exit(1) from None

    # Display results
    verdict_styles = {"passed": "green", "flagged": "yellow", "blocked": "red"}
    style = verdict_styles.get(report.verdict, "white")
    console.print(f"\n[bold {style}]Verdict: {report.verdict.upper()}[/bold {style}]")
    console.print(f"Files reviewed: {report.files_reviewed}")
    console.print(f"Screenshots scanned: {report.screenshots_scanned}")
    console.print(f"Run ID: {report.run_id}")

    if report.findings:
        severity_styles = {
            AuditSeverity.CRITICAL: "bold red",
            AuditSeverity.HIGH: "red",
            AuditSeverity.MEDIUM: "yellow",
            AuditSeverity.LOW: "cyan",
            AuditSeverity.INFO: "dim",
        }
        table = Table(show_header=True, title=f"Findings ({len(report.findings)})")
        table.add_column("Severity", width=10)
        table.add_column("Category", width=14)
        table.add_column("Title")
        table.add_column("File")

        for f in report.findings:
            s = severity_styles.get(f.severity, "")
            table.add_row(f.severity.value, f.category, f.title, f.file_path, style=s)
        console.print(table)

    if post_review:
        console.print("[green]Review posted to GitHub.[/green]")

    if report.verdict != "passed":
        raise typer.Exit(1)


@app.command()
def validate(
    path: str = typer.Argument(help="Path to docs directory or file to validate"),
) -> None:
    """Validate docs against the documentation standard and security scanners."""
    from pathlib import Path as PathObj

    from rich.table import Table

    from octoauthor.core.security import validate_content
    from octoauthor.core.security.models import FindingSeverity

    target = PathObj(path)
    if not target.exists():
        console.print(f"[red]Error:[/red] Path not found: {path}")
        raise typer.Exit(1)

    files = list(target.glob("**/*.md")) if target.is_dir() else [target]
    if not files:
        console.print(f"[yellow]No markdown files found in {path}[/yellow]")
        raise typer.Exit(0)

    severity_styles = {
        FindingSeverity.CRITICAL: "bold red",
        FindingSeverity.HIGH: "red",
        FindingSeverity.MEDIUM: "yellow",
        FindingSeverity.LOW: "cyan",
        FindingSeverity.INFO: "dim",
    }

    total_findings = 0
    total_files = 0

    for file_path in sorted(files):
        content = file_path.read_text()
        result = validate_content(content, str(file_path))
        total_files += 1

        if result.findings:
            total_findings += len(result.findings)
            console.print(f"\n[bold]{file_path}[/bold]")
            table = Table(show_header=True)
            table.add_column("Severity", width=10)
            table.add_column("Category", width=14)
            table.add_column("Message")
            table.add_column("Line", width=6, justify="right")

            for f in result.findings:
                style = severity_styles.get(f.severity, "")
                table.add_row(
                    f.severity.value,
                    f.category,
                    f.message,
                    str(f.line_number or ""),
                    style=style,
                )
            console.print(table)

    console.print(f"\n[bold]Scanned {total_files} files, found {total_findings} findings.[/bold]")
    if total_findings > 0:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()

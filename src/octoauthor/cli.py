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
        console.print("  all  (starts api + all MCP servers)")
        console.print("\n[dim]Ports are configured via .env (OCTOAUTHOR_ prefix)[/dim]")
        return

    if server == "all":
        _serve_all(host)
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
    repo: str = typer.Option("", help="GitHub repo (owner/name) to push docs to"),
) -> None:
    """Run the full documentation generation pipeline."""
    import asyncio

    from octoauthor.pipeline import run_pipeline

    console.print(f"Running OctoAuthor pipeline against [bold]{target}[/bold]...")
    console.print(f"Config: {config}")
    if dry_run:
        console.print("[yellow]DRY RUN - no files will be written[/yellow]")
    if repo:
        console.print(f"Target repo: [bold]{repo}[/bold]")

    try:
        asyncio.run(run_pipeline(config_path=config, target_url=target, dry_run=dry_run))
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None
    except Exception as e:
        console.print(f"[red]Pipeline error:[/red] {e}")
        raise typer.Exit(1) from None

    # Git integration: branch, commit, push, PR
    if repo and not dry_run:
        from octoauthor.core.config import get_settings

        settings = get_settings()
        token = settings.github_token
        if not token:
            console.print("[red]Error:[/red] OCTOAUTHOR_GITHUB_TOKEN required for --repo")
            raise typer.Exit(1)

        from pathlib import Path as PathObj

        from octoauthor.core.git import GitOps

        console.print(f"\n[bold]Pushing docs to {repo}...[/bold]")
        git = GitOps(repo=repo, token=token, branch_prefix=settings.github_branch_prefix)
        git.generate_branch_name()
        console.print(f"  Branch: {git.branch_name}")

        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            console.print("  Cloning (sparse)...")
            git.clone_sparse(PathObj(tmp))
            git.create_branch()

            doc_dir = settings.doc_output_dir
            file_count = git.commit_docs(doc_dir)
            console.print(f"  Committed {file_count} files")

            console.print("  Pushing...")
            git.push()
            console.print("  [green]Pushed![/green]")

            console.print("  Creating PR...")
            pr_url = asyncio.run(git.create_pr())
            console.print(f"  [bold green]PR created:[/bold green] {pr_url}")


@app.command()
def audit(
    pr: int = typer.Option(..., help="GitHub PR number to audit"),
    repo: str = typer.Option(..., help="GitHub repo (owner/name)"),
    post_review: bool = typer.Option(False, help="Post review to GitHub PR"),
    skip_llm: bool = typer.Option(False, help="Skip LLM review (security scanners only)"),
) -> None:
    """Run the auditor agent against a PR."""
    import asyncio

    from rich.table import Table

    from octoauthor.auditor import run_audit
    from octoauthor.core.config import get_settings
    from octoauthor.core.models.agents import AuditSeverity

    token = get_settings().github_token or ""
    if not token:
        console.print("[red]Error:[/red] OCTOAUTHOR_GITHUB_TOKEN is required (set in .env or environment)")
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
def auth(
    target: str = typer.Option(..., help="Base URL of the target app to log into"),
    output: str = typer.Option(".octoauthor/auth/storage-state.json", help="Where to save the session state"),
) -> None:
    """Open a browser for manual login, then save the session state for automated runs."""
    import asyncio

    async def _capture_session() -> None:
        from playwright.async_api import async_playwright

        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(target)

        console.print(f"\nBrowser opened to [bold]{target}[/bold]")
        console.print("Log in manually, then press [bold green]Enter[/bold green] here when done...")
        input()

        from pathlib import Path as PathObj

        out_path = PathObj(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        await context.storage_state(path=str(out_path))
        await browser.close()
        await pw.stop()
        console.print(f"Session saved to [green]{output}[/green]")
        console.print("\nAdd this to your config:")
        console.print(f"  auth:\n    strategy: storage_state\n    storage_state_path: {output}")

    asyncio.run(_capture_session())


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


def _serve_all(host: str) -> None:
    """Launch all MCP servers + discovery API in parallel processes."""
    import signal
    import sys
    from multiprocessing import Process

    from octoauthor.core.config import get_settings

    settings = get_settings()
    processes: list[Process] = []

    def _run_api() -> None:
        import uvicorn

        from octoauthor.service import create_app

        uvicorn.run(create_app(), host=host, port=settings.api_port, log_level="info")

    def _run_mcp(name: str, port: int) -> None:
        from octoauthor.mcp_servers.registry import create_server

        srv = create_server(name)
        srv.settings.host = host
        srv.settings.port = port
        srv.run(transport="sse")

    # Start API server
    api_proc = Process(target=_run_api, name="api", daemon=True)
    api_proc.start()
    processes.append(api_proc)
    console.print(f"  [green]api[/green] on {host}:{settings.api_port}")

    # Start MCP servers
    from octoauthor.mcp_servers.registry import get_server_ports

    for name, port in get_server_ports().items():
        proc = Process(target=_run_mcp, args=(name, port), name=name, daemon=True)
        proc.start()
        processes.append(proc)
        console.print(f"  [green]{name}[/green] on {host}:{port}")

    console.print(f"\n[bold]All {len(processes)} services started.[/bold] Press Ctrl+C to stop.")

    def _shutdown(signum: int, frame: object) -> None:
        console.print("\n[yellow]Shutting down...[/yellow]")
        for p in processes:
            p.terminate()
        for p in processes:
            p.join(timeout=5)
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Wait for any process to exit (indicates failure)
    while True:
        for p in processes:
            p.join(timeout=1)
            if not p.is_alive() and p.exitcode is not None and p.exitcode != 0:
                console.print(f"[red]{p.name} exited with code {p.exitcode}[/red]")
                _shutdown(0, None)


if __name__ == "__main__":
    app()

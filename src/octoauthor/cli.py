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
    server: str = typer.Argument(help="MCP server to run (e.g., 'screenshot-server')"),
    port: int = typer.Option(8000, help="Port to listen on"),
) -> None:
    """Run a specific MCP server for development."""
    console.print(f"Starting {server} on port {port}...")
    # TODO: Implement MCP server startup
    console.print("[yellow]Not yet implemented[/yellow]")


@app.command()
def run(
    config: str = typer.Option("config.yaml", help="Path to capture config file"),
    target: str = typer.Option(..., help="Path to target project or base URL"),
    dry_run: bool = typer.Option(False, help="Preview what would be generated without writing"),
) -> None:
    """Run the full documentation generation pipeline."""
    console.print(f"Running OctoAuthor pipeline against {target}...")
    console.print(f"Config: {config}")
    if dry_run:
        console.print("[yellow]DRY RUN - no files will be written[/yellow]")
    # TODO: Implement pipeline orchestration
    console.print("[yellow]Not yet implemented[/yellow]")


@app.command()
def audit(
    pr: int = typer.Option(..., help="GitHub PR number to audit"),
    repo: str = typer.Option(..., help="GitHub repo (owner/name)"),
) -> None:
    """Run the auditor agent against a PR."""
    console.print(f"Auditing PR #{pr} on {repo}...")
    # TODO: Implement audit runner
    console.print("[yellow]Not yet implemented[/yellow]")


@app.command()
def validate(
    path: str = typer.Argument(help="Path to docs directory to validate against doc-standard"),
) -> None:
    """Validate existing docs against the documentation standard."""
    console.print(f"Validating docs at {path}...")
    # TODO: Implement doc validation
    console.print("[yellow]Not yet implemented[/yellow]")


if __name__ == "__main__":
    app()

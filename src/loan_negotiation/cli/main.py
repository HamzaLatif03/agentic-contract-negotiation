import asyncio

import typer

from loan_negotiation.agents.factory import check_ollama_connection
from loan_negotiation.config import get_settings

app = typer.Typer()


@app.command("status")
def status() -> None:
    """Check Ollama connectivity."""
    settings = get_settings()

    try:
        result = asyncio.run(check_ollama_connection(settings))
    except Exception as exc:
        typer.echo(f"Connection failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    available = "yes" if result["model_available"] else "no"
    typer.echo(f"{result['host']}  model={result['model']}  available={available}")

    if not result["model_available"]:
        raise typer.Exit(code=1)


@app.command("run")
def run() -> None:
    """Run the loan negotiation workflow."""
    typer.echo("Workflow not yet implemented.", err=True)
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()

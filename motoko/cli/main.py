"""Main CLI entrypoint for motoko."""

import typer
from typing_extensions import Annotated

from .chat import chat_command

app = typer.Typer(
    name="motoko",
    help="Interactive AI agent CLI powered by Claude and Gemini",
    add_completion=False,
)


@app.command()
def version():
    """Show motoko version."""
    from motoko import __version__
    typer.echo(f"motoko version {__version__}")


@app.command()
def chat(
    model: Annotated[
        str,
        typer.Option(
            "--model",
            "-m",
            help="Model to use (e.g., gemini-3-pro-preview, claude-sonnet-4-5-20250929)",
        ),
    ] = "gemini-3-pro-preview",
    workspace: Annotated[
        str | None,
        typer.Option(
            "--workspace",
            "-w",
            help="Workspace directory for file tools",
        ),
    ] = None,
    tools: Annotated[
        str | None,
        typer.Option(
            "--tools",
            "-t",
            help="Comma-separated list of tools to enable (e.g., read,write,glob)",
        ),
    ] = None,
    all_tools: Annotated[
        bool,
        typer.Option(
            "--all-tools/--no-tools",
            help="Enable all available tools",
        ),
    ] = True,
    temperature: Annotated[
        float | None,
        typer.Option(
            "--temperature",
            help="Sampling temperature (0.0-1.0)",
        ),
    ] = None,
    stream: Annotated[
        bool,
        typer.Option(
            "--stream/--no-stream",
            help="Enable streaming responses",
        ),
    ] = True,
):
    """Start an interactive chat session."""
    chat_command(
        model=model,
        workspace=workspace,
        tools=tools,
        all_tools=all_tools,
        temperature=temperature,
        stream=stream,
    )


def cli():
    """CLI entrypoint."""
    app()


if __name__ == "__main__":
    cli()

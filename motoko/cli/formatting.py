"""Output formatting for CLI using rich - Claude Code style."""

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

console = Console()


class OutputFormatter:
    """Claude Code-style output formatter."""

    def __init__(self):
        self.current_live = None
        self.tool_count = 0

    def print_task(self, message: str):
        """Print user's task/request."""
        console.print()
        console.print(Panel(
            f"[bold cyan]{message}[/bold cyan]",
            title="[bold]Your Request[/bold]",
            border_style="cyan",
            padding=(0, 2),
        ))
        console.print()

    def print_thinking(self, text: str):
        """Print AI thinking/planning."""
        if text:
            console.print(f"[dim italic]{text}[/dim italic]")

    def start_tool_execution(self, tool_name: str, tool_input: dict):
        """Show tool execution starting."""
        self.tool_count += 1

        # Create input table
        if tool_input:
            input_table = Table.grid(padding=(0, 1))
            input_table.add_column(style="dim")
            input_table.add_column()

            for key, value in tool_input.items():
                # Truncate long values
                value_str = str(value)
                if len(value_str) > 100:
                    value_str = value_str[:100] + "..."
                input_table.add_row(f"{key}:", value_str)

            console.print()
            console.print(Panel(
                input_table,
                title=f"[bold yellow]🔧 Tool {self.tool_count}: {tool_name}[/bold yellow]",
                border_style="yellow",
                padding=(0, 1),
            ))
        else:
            console.print()
            console.print(f"[yellow]🔧 Tool {self.tool_count}: {tool_name}[/yellow]")

    def end_tool_execution(self, tool_name: str, result: str, is_error: bool = False):
        """Show tool execution result."""
        if is_error:
            console.print(Panel(
                f"[red]{result}[/red]",
                title=f"[bold red]❌ {tool_name} - Error[/bold red]",
                border_style="red",
                padding=(0, 1),
            ))
        else:
            # Truncate long results
            display_result = result
            if len(result) > 500:
                display_result = result[:500] + f"\n\n[dim]... ({len(result)} characters total)[/dim]"

            console.print(Panel(
                display_result,
                title=f"[bold green]✓ {tool_name} - Success[/bold green]",
                border_style="green",
                padding=(0, 1),
            ))

    def print_response_start(self):
        """Print response section header."""
        console.print()
        console.print("[bold green]Assistant:[/bold green]")

    def print_response_chunk(self, chunk: str):
        """Print streaming text chunk."""
        console.print(chunk, end="")

    def print_response_end(self):
        """Print response section footer."""
        console.print()  # Final newline

    def print_file_content(self, path: str, content: str, language: str = ""):
        """Print file content with syntax highlighting."""
        syntax = Syntax(content, language or "text", theme="monokai", line_numbers=True)
        console.print()
        console.print(Panel(
            syntax,
            title=f"[bold]{path}[/bold]",
            border_style="blue",
        ))

    def print_error(self, message: str):
        """Print error message."""
        console.print()
        console.print(Panel(
            f"[bold red]{message}[/bold red]",
            title="[bold]Error[/bold]",
            border_style="red",
            padding=(0, 1),
        ))

    def print_system(self, message: str):
        """Print system message."""
        console.print(f"[dim]{message}[/dim]")

    def print_welcome(self):
        """Print welcome message - Claude Code style."""
        welcome = Text()
        welcome.append("motoko", style="bold cyan")
        welcome.append(" - AI Agent CLI\n", style="bold")
        welcome.append("Powered by Gemini 3 Pro and Claude Sonnet 4.5\n\n", style="dim")
        welcome.append("Commands:\n", style="bold")
        welcome.append("  /exit, /quit  ", style="cyan")
        welcome.append("- Exit the session\n", style="dim")
        welcome.append("  /model <name> ", style="cyan")
        welcome.append("- Switch model\n", style="dim")
        welcome.append("  /clear        ", style="cyan")
        welcome.append("- Clear history\n", style="dim")
        welcome.append("  /help         ", style="cyan")
        welcome.append("- Show help\n", style="dim")

        console.print(Panel(welcome, border_style="cyan", padding=(1, 2)))
        console.print()

    def print_help(self):
        """Print help message."""
        help_table = Table.grid(padding=(0, 2))
        help_table.add_column(style="cyan bold")
        help_table.add_column(style="dim")

        help_table.add_row("/exit, /quit", "Exit the session")
        help_table.add_row("/model <name>", "Switch to a different model")
        help_table.add_row("/role <name>", "Switch to a role")
        help_table.add_row("/roles", "List available roles")
        help_table.add_row("/clear", "Clear conversation history")
        help_table.add_row("/help", "Show this help message")

        console.print()
        console.print(Panel(
            help_table,
            title="[bold]Available Commands[/bold]",
            border_style="cyan",
            padding=(1, 2),
        ))
        console.print()

    def print_session_info(self, model: str, workspace: str, tools_enabled: bool):
        """Print session information."""
        info_table = Table.grid(padding=(0, 1))
        info_table.add_column(style="dim")
        info_table.add_column()

        info_table.add_row("Model:", f"[cyan]{model}[/cyan]")
        info_table.add_row("Workspace:", f"[blue]{workspace}[/blue]")
        info_table.add_row("Tools:", "[green]Enabled[/green]" if tools_enabled else "[dim]Disabled[/dim]")

        console.print()
        console.print(Panel(
            info_table,
            title="[bold]Session Info[/bold]",
            border_style="dim",
            padding=(0, 1),
        ))
        console.print()


# Global formatter instance
formatter = OutputFormatter()


# Convenience functions
def print_task(message: str):
    formatter.print_task(message)


def print_thinking(text: str):
    formatter.print_thinking(text)


def start_tool_execution(tool_name: str, tool_input: dict):
    formatter.start_tool_execution(tool_name, tool_input)


def end_tool_execution(tool_name: str, result: str, is_error: bool = False):
    formatter.end_tool_execution(tool_name, result, is_error)


def print_response_start():
    formatter.print_response_start()


def print_response_chunk(chunk: str):
    formatter.print_response_chunk(chunk)


def print_response_end():
    formatter.print_response_end()


def print_file_content(path: str, content: str, language: str = ""):
    formatter.print_file_content(path, content, language)


def print_error(message: str):
    formatter.print_error(message)


def print_system(message: str):
    formatter.print_system(message)


def print_welcome():
    formatter.print_welcome()


def print_help():
    formatter.print_help()


def print_session_info(model: str, workspace: str, tools_enabled: bool):
    formatter.print_session_info(model, workspace, tools_enabled)

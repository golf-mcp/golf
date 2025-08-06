"""Golf CLI branding and visual utilities."""

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align

# Golf brand colors (official brand colors)
GOLF_BLUE = "#2969FD"  # Primary blue from brand: rgb(41, 105, 253)
GOLF_ORANGE = "#F97728"  # Secondary orange from brand: rgb(249, 119, 40)
GOLF_GREEN = "#10B981"  # Success green
GOLF_WHITE = "#FFFFFF"

# Simple GolfMCP text logo
GOLF_LOGO = """
 ██████╗  ██████╗ ██╗     ███████╗███╗   ███╗ ██████╗██████╗ 
██╔════╝ ██╔═══██╗██║     ██╔════╝████╗ ████║██╔════╝██╔══██╗
██║  ███╗██║   ██║██║     █████╗  ██╔████╔██║██║     ██████╔╝
██║   ██║██║   ██║██║     ██╔══╝  ██║╚██╔╝██║██║     ██╔═══╝ 
╚██████╔╝╚██████╔╝███████╗██║     ██║ ╚═╝ ██║╚██████╗██║     
 ╚═════╝  ╚═════╝ ╚══════╝╚═╝     ╚═╝     ╚═╝ ╚═════╝╚═╝     
"""

# Simplified version for smaller spaces
GOLF_LOGO_SMALL = "Golf"

# Status icons with consistent styling
STATUS_ICONS = {
    "success": "✓",
    "error": "✗",
    "warning": "⚠",
    "info": "ℹ",
    "building": "🔨",
    "generating": "⚙️",
    "packaging": "📦",
    "platform": "⛳",
    "server": "🚀",
    "loading": "⭕",
}


def create_welcome_banner(version: str, console: Console) -> None:
    """Create the main Golf welcome banner."""
    # Create the logo with Golf in blue and MCP in orange
    logo_lines = GOLF_LOGO.strip().split("\n")
    logo_content = Text()

    for line in logo_lines:
        if line.strip():  # Only process non-empty lines
            # Find where "MCP" starts (roughly at position 32 in the ASCII art)
            golf_part = line[:32]  # First part is "Golf"
            mcp_part = line[32:]  # Last part is "MCP"

            logo_content.append(golf_part, style=f"bold {GOLF_BLUE}")
            logo_content.append(mcp_part, style=f"bold {GOLF_ORANGE}")
        logo_content.append("\n")

    # Create version line
    version_text = Text()
    version_text.append("🚀 ", style=f"bold {GOLF_ORANGE}")
    version_text.append(f"Golf v{version}", style=f"bold {GOLF_BLUE}")
    version_text.append(" 🚀", style=f"bold {GOLF_ORANGE}")

    # Create tagline
    tagline_text = Text("✨ Easiest way to build production-ready MCP servers ✨", style="bold white")

    # Create the full content using a renderable group approach
    from rich.console import Group

    content_group = Group(
        Align.center(logo_content),
        "",  # Empty line for spacing
        Align.center(version_text),
        Align.center(tagline_text),
    )

    panel = Panel(
        content_group,
        border_style=GOLF_BLUE,
        padding=(1, 2),
        title="[bold]🏌️ Welcome to Golf 🏌️[/bold]",
        title_align="center",
    )

    console.print(panel)


def create_command_header(title: str, subtitle: str = "", console: Console | None = None) -> None:
    """Create a styled command header."""
    if console is None:
        console = Console()

    header = Text()
    header.append("🏌️ ", style=f"bold {GOLF_ORANGE}")
    header.append(title, style=f"bold {GOLF_BLUE}")

    if subtitle:
        header.append(f" → {subtitle}", style=f"bold {GOLF_ORANGE}")

    # Create a stylish panel for the header
    panel = Panel(
        Align.center(header),
        border_style=GOLF_BLUE,
        padding=(0, 2),
    )

    console.print(panel)


def create_success_message(message: str, console: Console | None = None) -> None:
    """Create a styled success message."""
    if console is None:
        console = Console()

    success_content = Text()
    success_content.append("🎉 ", style=f"bold {GOLF_ORANGE}")
    success_content.append(f"{STATUS_ICONS['success']} {message}", style=f"bold {GOLF_GREEN}")
    success_content.append(" 🎉", style=f"bold {GOLF_ORANGE}")

    success_panel = Panel(
        Align.center(success_content),
        border_style=GOLF_GREEN,
        padding=(0, 2),
        title="[bold green]SUCCESS[/bold green]",
        title_align="center",
    )
    console.print(success_panel)


def create_info_panel(title: str, content: str, console: Console | None = None) -> None:
    """Create a styled info panel."""
    if console is None:
        console = Console()

    # Add some visual flair to the content
    styled_content = Text()
    for line in content.split("\n"):
        if line.strip():
            styled_content.append("▶ ", style=f"bold {GOLF_ORANGE}")
            styled_content.append(line, style="bold white")
            styled_content.append("\n")

    panel = Panel(
        styled_content,
        title=f"[bold {GOLF_BLUE}]🔧 {title} 🔧[/bold {GOLF_BLUE}]",
        border_style=GOLF_BLUE,
        padding=(1, 2),
    )
    console.print(panel)


def get_status_text(status: str, message: str, style: str = "") -> Text:
    """Get formatted status text with icon."""
    icon = STATUS_ICONS.get(status, "•")
    text = Text()

    if status == "success":
        text.append("🎉 ", style=f"bold {GOLF_ORANGE}")
        text.append(f"{icon} {message}", style=f"bold {GOLF_GREEN}")
    elif status == "error":
        text.append("💥 ", style=f"bold {GOLF_ORANGE}")
        text.append(f"{icon} {message}", style="bold red")
    elif status == "warning":
        text.append("⚡ ", style=f"bold {GOLF_ORANGE}")
        text.append(f"{icon} {message}", style=f"bold {GOLF_ORANGE}")
    elif status in ["building", "generating", "packaging", "platform"]:
        text.append("🔥 ", style=f"bold {GOLF_ORANGE}")
        text.append(f"{icon} {message}", style=f"bold {GOLF_BLUE}")
    else:
        text.append("💡 ", style=f"bold {GOLF_ORANGE}")
        text.append(f"{icon} {message}", style=f"bold {GOLF_BLUE}")

    return text


def create_build_header(project_name: str, environment: str, console: Console) -> None:
    """Create a styled build process header."""
    title = Text()
    title.append("🔨 Building ", style=f"bold {GOLF_ORANGE}")
    title.append(project_name, style=f"bold {GOLF_BLUE}")
    title.append(f" ({environment} environment)", style=f"bold {GOLF_GREEN}")

    # Create a flashy build panel
    panel = Panel(
        Align.center(title),
        border_style=GOLF_ORANGE,
        padding=(0, 2),
        title="[bold]🚧 BUILD IN PROGRESS 🚧[/bold]",
        title_align="center",
    )

    console.print(panel)

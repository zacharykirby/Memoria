"""
UI components and display helpers using Rich.
Clean, minimal chat interface with subtle cyberpunk accents.
Input handled by prompt_toolkit for proper multiline / history support.
"""

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.spinner import Spinner
from rich.text import Text
from rich.style import Style
from rich.theme import Theme

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import FormattedText

# ── Theme ──────────────────────────────────────────────────────────────

CYBER_THEME = Theme({
    "cyan": "#00D9FF",
    "magenta": "#FF10F0",
    "neon_green": "#39FF14",
    "dim_cyan": "dim #00D9FF",
    "bright_white": "bright_white",
})

console = Console(theme=CYBER_THEME)

# Named styles (exported for other modules)
STYLE_ACCENT = Style(color="#00D9FF")
STYLE_DIM_ACCENT = Style(color="#00D9FF", dim=True)
STYLE_SUCCESS = Style(color="#39FF14", dim=True)
STYLE_ERROR = Style(color="#FF10F0", dim=True)

# Legacy aliases (onboarding.py imports STYLE_SUCCESS)
STYLE_TOOL_CALL = STYLE_DIM_ACCENT
STYLE_TOOL_RESULT = STYLE_DIM_ACCENT
STYLE_THINKING = STYLE_DIM_ACCENT
STYLE_PROMPT = STYLE_ACCENT

# ── Tool descriptions ─────────────────────────────────────────────────

TOOL_SPINNER_TEXT = {
    "read_core_memory":   "recalling...",
    "read_memory":        "recalling...",
    "read_memory_note":   "recalling...",
    "read_archive":       "recalling...",
    "write_memory":       "remembering...",
    "update_core_memory": "updating...",
    "create_memory_note": "remembering...",
    "update_memory_note": "remembering...",
    "delete_memory_note": "forgetting...",
    "search_vault":       "searching...",
    "update_soul":        "reflecting...",
    "archive_memory":     "archiving...",
    "list_memory_notes":  "browsing...",
}


def tool_completion_summary(func_name: str, args: dict) -> str:
    """Human-readable one-liner for a completed tool call."""
    detail = (
        args.get("path")
        or args.get("filename")
        or args.get("title")
        or args.get("query")
        or ""
    )
    if func_name == "read_core_memory":
        return "recalled core memory"
    if func_name in ("read_memory", "read_memory_note"):
        return f"recalled {detail}" if detail else "recalled memory"
    if func_name == "read_archive":
        d = args.get("date", "")
        return f"recalled archive {d}".strip()
    if func_name in ("write_memory", "create_memory_note"):
        return f"remembered {detail}" if detail else "saved to memory"
    if func_name == "update_core_memory":
        return "updated core memory"
    if func_name == "update_memory_note":
        return f"updated {detail}" if detail else "updated note"
    if func_name == "delete_memory_note":
        return f"forgot {detail}" if detail else "deleted note"
    if func_name == "search_vault":
        return f"searched for '{detail}'" if detail else "searched vault"
    if func_name == "update_soul":
        file = args.get("file", "soul")
        return f"reflected ({file})" if file != "soul" else "reflected"
    if func_name == "archive_memory":
        return "archived"
    if func_name == "list_memory_notes":
        return "browsed memory"
    return "done"


# ── Spinners ───────────────────────────────────────────────────────────

def make_spinner(message: str) -> Spinner:
    """Create a diamond-alternating spinner renderable with a message."""
    s = Spinner("dots", text=Text(message, style="dim #00D9FF"), style="dim #00D9FF")
    s.frames = ["◆", "◇"]
    s.interval = 500
    return s


def start_spinner(message: str) -> Live:
    """Start an animated spinner. Returns Live instance — call .stop() when done."""
    live = Live(
        make_spinner(message),
        console=console,
        refresh_per_second=4,
        transient=True,
    )
    live.start()
    return live


# ── Streaming display ─────────────────────────────────────────────────

class StreamingDisplay:
    """Manages the spinner → streaming content transition.

    Shows an animated spinner until the first content token arrives,
    then transitions to a live-updating Markdown display.

    Passed as ``live_display`` to call_llm — only needs an .update() method.
    """

    def __init__(self):
        self._spinner_live = Live(
            make_spinner("thinking..."),
            console=console,
            refresh_per_second=4,
            transient=True,
        )
        self._content_live = None
        self._content_started = False

    def start(self):
        self._spinner_live.start()

    def update(self, renderable):
        """Called by call_llm each time new content arrives."""
        if not self._content_started:
            self._content_started = True
            self._spinner_live.stop()
            console.print()
            console.print(Text("mem", style="dim #00D9FF"))
            self._content_live = Live(
                renderable,
                console=console,
                refresh_per_second=15,
                transient=False,
            )
            self._content_live.start()
        else:
            self._content_live.update(renderable)

    def stop(self):
        """Clean up whichever Live is still active."""
        if self._content_started and self._content_live:
            try:
                self._content_live.stop()
            except Exception:
                pass
        elif not self._content_started:
            try:
                self._spinner_live.stop()
            except Exception:
                pass


# ── Display functions ──────────────────────────────────────────────────

def display_startup():
    """One-line header: app name + model, dim and unobtrusive."""
    console.print()
    try:
        from llm import LLM_MODEL
        header = Text()
        header.append("  memoria", style="dim #00D9FF")
        header.append(f"  //  {LLM_MODEL}", style="dim")
        console.print(header)
    except ImportError:
        console.print(Text("  memoria", style="dim #00D9FF"))
    console.print()


# ── Input (prompt_toolkit) ─────────────────────────────────────────────
# Enter submits.  Bracketed paste mode (enabled by default in
# prompt_toolkit) lets multiline pastes land in the buffer without
# triggering submit mid-paste.  PromptSession keeps in-memory history;
# Up/Down arrows cycle through it.
#
# Session is created lazily so that importing ui.py in environments
# without a real console (e.g. pytest) doesn't blow up.

_prompt_text = FormattedText([("#00D9FF bold", "you"), ("", "  ")])
_session: PromptSession | None = None


def get_user_input() -> str:
    """Get user input with 'you' prefix. Returns 'quit' on Ctrl+C/Ctrl+D."""
    global _session
    if _session is None:
        _session = PromptSession()
    console.print()
    try:
        text = _session.prompt(_prompt_text)
        return text.strip()
    except (KeyboardInterrupt, EOFError):
        console.print()
        return "quit"


def display_status(tokens: int, session: int):
    """Dim status line between response and next prompt."""
    console.print(Text(f"  ↳ {tokens:,} tokens  ·  session {session}", style="dim"))


def display_response(content: str):
    """Display assistant response with 'mem' label and Markdown rendering."""
    if not content:
        return
    console.print()
    console.print(Text("mem", style="dim #00D9FF"))
    console.print(Markdown(content))


def display_error(message: str):
    """Display a subtle, non-alarming error."""
    console.print(Text(f"  {message}", style="dim #FF10F0"))


def display_tool_done(func_name: str, args: dict):
    """Print a dim completion line after a tool finishes."""
    summary = tool_completion_summary(func_name, args)
    console.print(Text(f"  ◆ {summary}", style="dim #555555"))


# ── Legacy compatibility shims ─────────────────────────────────────────
# run_agent_loop now handles tool display via spinners.
# These are kept so older call-sites don't break.

def display_tool_call(func_name: str, args: dict):
    """Legacy no-op — tool display is now animated spinners in the agent loop."""
    pass


def display_tool_result(result: str):
    """Legacy no-op — raw tool output is never shown."""
    pass


def display_thinking():
    """Legacy no-op — thinking is now an animated spinner."""
    pass


def display_welcome(core_memory: str = ""):
    """Legacy — redirects to minimal startup."""
    display_startup()

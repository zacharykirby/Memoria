# chat.py
"""Local Memory Assistant - Main entry point."""
import argparse
import sys
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from memory import (
    read_core_memory,
    ensure_memory_structure,
    memory_exists,
    delete_ai_memory_folder,
    reset_soul_folder,
)
from prompts import build_system_prompt, FIRST_CONVERSATION_OPENER, FIRST_CONVERSATION_NOTE
from tools import CHAT_TOOLS, parse_tool_arguments, execute_tool
from consolidation import run_consolidation
import os
from dotenv import load_dotenv

from rich.prompt import Prompt
from rich.text import Text

from ui import console, display_startup, display_response, display_status, get_user_input
from llm import run_agent_loop, truncate_messages, MAX_MESSAGES_IN_CONTEXT

load_dotenv()


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Local Memory Assistant")
    parser.add_argument(
        "--reset-memory",
        action="store_true",
        help="Wipe user memory (preserves soul) and start fresh",
    )
    parser.add_argument(
        "--refresh-memory",
        action="store_true",
        dest="reset_memory",
        help="Alias for --reset-memory",
    )
    parser.add_argument(
        "--reset-soul",
        action="store_true",
        help="Reset Memoria's soul directory to defaults",
    )
    return parser.parse_args()


def _confirm_reset() -> bool:
    """Ask user to confirm memory reset. Returns True if confirmed."""
    try:
        confirm = Prompt.ask("Delete existing memory and start fresh?", choices=["yes", "no"], default="no")
        return confirm.lower() == "yes"
    except (EOFError, KeyboardInterrupt):
        return False


def _build_system_content(core_section: str, first_conversation: bool = False) -> str:
    """Build system message content with current core memory and live memory map."""
    base = build_system_prompt()
    if first_conversation:
        return base + "\n\n" + FIRST_CONVERSATION_NOTE + "\n\n## Core memory (current)\n\n(Empty — first conversation.)"
    if core_section:
        return base + "\n\n## Core memory (current)\n\n" + core_section
    return base + "\n\n## Core memory (current)\n\n(Empty. Use update_core_memory when you learn something about the user.)"


def _refresh_system_message(messages: list) -> str:
    """Re-read core memory from disk and update the system message in place. Returns the new core section."""
    core_section = read_core_memory()
    messages[0] = {"role": "system", "content": _build_system_content(core_section)}
    return core_section


def _get_session_number() -> int:
    """Read and increment persistent session counter (stored in vault root)."""
    vault_path = os.getenv("OBSIDIAN_PATH")
    if not vault_path:
        return 1
    session_file = Path(vault_path) / ".memoria_session"
    try:
        n = int(session_file.read_text().strip())
    except (FileNotFoundError, ValueError):
        n = 0
    n += 1
    try:
        session_file.write_text(str(n))
    except OSError:
        pass
    return n


def _estimate_tokens(messages: list) -> int:
    """Rough token estimate from message content (~4 chars per token)."""
    total = sum(len(m.get("content", "") or "") for m in messages)
    return total // 4


def _run_agent_loop(initial_messages, tools, max_messages_in_context=MAX_MESSAGES_IN_CONTEXT, **kwargs):
    """Wrapper that passes truncate_messages to run_agent_loop."""
    return run_agent_loop(
        initial_messages,
        tools,
        truncate_fn=truncate_messages,
        max_messages_in_context=max_messages_in_context,
        **kwargs,
    )


def main():
    args = parse_args()

    # Handle soul reset (standalone or combined with --reset-memory)
    if args.reset_soul:
        try:
            confirm = Prompt.ask(
                "Reset Memoria's soul to defaults? This erases her sense of self.",
                choices=["yes", "no"],
                default="no",
            )
        except (EOFError, KeyboardInterrupt):
            confirm = "no"
        if confirm.lower() != "yes":
            console.print("Cancelled.")
            if not args.reset_memory:
                return
        else:
            result = reset_soul_folder()
            if not result.get("success"):
                console.print(f"[bold #FF10F0]Error: {result.get('error', 'Unknown')}[/bold #FF10F0]")
                return
            console.print("  Soul reset to defaults.", style="dim")
            if not args.reset_memory:
                return

    # Handle memory reset (preserves soul/)
    if args.reset_memory:
        if memory_exists():
            if not _confirm_reset():
                console.print("Cancelled.")
                return
            result = delete_ai_memory_folder()
            if not result.get("success"):
                console.print(f"[bold #FF10F0]Error: {result.get('error', 'Unknown')}[/bold #FF10F0]")
                return
        # Fall through to normal startup (will be treated as first conversation)

    # Normal startup
    first_conversation = not memory_exists()

    init_result = ensure_memory_structure()
    if not init_result.get("success"):
        console.print(f"[bold #FF10F0]Memory init error: {init_result.get('error', 'Unknown')}[/bold #FF10F0]")
        return

    core_section = read_core_memory()
    session_number = _get_session_number()

    if first_conversation:
        display_startup()
        display_response(FIRST_CONVERSATION_OPENER)
        messages = [
            {"role": "system", "content": _build_system_content(core_section, first_conversation=True)},
            {"role": "assistant", "content": FIRST_CONVERSATION_OPENER},
        ]
    else:
        display_startup()
        messages = [{"role": "system", "content": _build_system_content(core_section)}]

    while True:
        user_input = get_user_input()

        if user_input.lower() in ['quit', 'exit']:
            console.print()
            run_consolidation(messages)
            goodbye = Text("Goodbye!", style="bold #FF10F0")
            console.print(goodbye)
            break

        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})

        result = _run_agent_loop(
            messages,
            CHAT_TOOLS,
            max_iterations=10,
            stream_first_response=True,
            show_tool_calls=True,
        )
        messages = result["messages"]

        # Refresh system message so core memory stays current after tool updates
        core_section = _refresh_system_message(messages)

        display_status(_estimate_tokens(messages), session_number)


if __name__ == "__main__":
    main()

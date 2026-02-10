"""
Memory consolidation on conversation end.

Handles reviewing conversation history and updating memory intelligently
using an agentic loop.
"""

from ui import console
from llm import run_agent_loop, truncate_messages, CONSOLIDATION_MAX_MESSAGES
from prompts import CONSOLIDATION_SYSTEM_PROMPT, build_consolidation_user_message
from tools import CONSOLIDATION_TOOLS
from memory import read_core_memory


def run_consolidation(messages: list) -> None:
    """Run memory consolidation using an agentic loop: LLM can read memory, then update based on results."""
    console.print("\n╭─ CONSOLIDATING MEMORY ─" + "─" * 44 + "╮", style="cyan")
    console.print("│ Reviewing conversation and updating memory..." + " " * 18 + "│")
    console.print("╰─" + "─" * 68 + "╯\n")

    core_content = read_core_memory()
    user_consolidation_msg = build_consolidation_user_message(messages, core_content)

    consolidation_messages = [
        {"role": "system", "content": CONSOLIDATION_SYSTEM_PROMPT},
        {"role": "user", "content": user_consolidation_msg},
    ]

    result = run_agent_loop(
        consolidation_messages,
        CONSOLIDATION_TOOLS,
        truncate_fn=truncate_messages,
        max_messages_in_context=CONSOLIDATION_MAX_MESSAGES,
        max_iterations=10,
        stream_first_response=False,
        show_tool_calls=True,
    )

    if result["iterations"] >= 10:
        console.print("\n[yellow]Warning: Consolidation hit max iterations[/yellow]\n")

    console.print("\n✓ Memory consolidation complete\n", style="green")

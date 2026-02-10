"""
User onboarding and memory initialization flows.

Handles:
- Adaptive Q&A for memory seeding
- Exploratory conversation mode
- Memory extraction from conversations
- Initial memory structure generation
"""

from typing import Optional

from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

from ui import console, STYLE_SUCCESS
from llm import call_llm, extract_json_from_response
from prompts import (
    ONBOARDING_QUESTIONS,
    MEMORY_GENERATION_PROMPT,
    INITIAL_QUESTIONS_PROMPT,
    REFRESH_QUESTIONS_PROMPT,
    FALLBACK_INITIAL_QUESTIONS,
    FALLBACK_REFRESH_QUESTIONS,
    UPDATE_MEMORY_PROMPT,
    EXPLORATION_PROMPT,
    build_exploration_extraction_prompt,
)
from memory import (
    read_core_memory,
    update_core_memory,
    read_context,
    update_context,
    archive_memory,
    ensure_memory_structure,
    load_all_memory,
    memory_exists,
    write_organized_memory as memory_write_organized,
)


def generate_questions(memory_exists_flag: bool, memory_content: Optional[dict] = None) -> dict:
    """
    Generate contextual questions based on existing memory state.

    Returns:
        {"skip": bool, "reason": str, "questions": list[str]}
    """
    system_msg = "You output only valid JSON. No markdown, no explanation."

    if not memory_exists_flag:
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": INITIAL_QUESTIONS_PROMPT},
        ]
    else:
        content = memory_content or {}
        prompt = REFRESH_QUESTIONS_PROMPT.format(
            core_memory_content=content.get("core_memory") or "(empty)",
            personal_context=content.get("personal") or "(empty)",
            work_context=content.get("work") or "(empty)",
            current_focus_context=content.get("current_focus") or "(empty)",
            preferences_context=content.get("preferences") or "(empty)",
        )
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt},
        ]

    for attempt in range(2):
        response = call_llm(messages, tools=None, stream=False)
        if not response:
            continue
        raw = (response.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        parsed = extract_json_from_response(raw)
        if not parsed:
            continue

        if parsed.get("skip") is True:
            return {
                "skip": True,
                "reason": (parsed.get("reason") or "Memory appears current and comprehensive").strip(),
                "questions": [],
            }

        questions = parsed.get("questions")
        if isinstance(questions, list) and len(questions) > 0:
            return {"skip": False, "reason": "", "questions": [str(q).strip() for q in questions]}

    if memory_exists_flag:
        return {"skip": False, "reason": "", "questions": FALLBACK_REFRESH_QUESTIONS}
    return {"skip": False, "reason": "", "questions": FALLBACK_INITIAL_QUESTIONS}


def _is_qa_format(answers: dict) -> bool:
    """True if answers are in adaptive Q&A format: { q1: {question, answer}, ... }."""
    if not answers:
        return False
    first = next(iter(answers.values()), None)
    return isinstance(first, dict) and "question" in first and "answer" in first


def _template_fallback_memory(answers: dict) -> dict:
    """Build minimal memory content from answers when LLM generation fails."""
    if _is_qa_format(answers):
        qa_lines = []
        for v in answers.values():
            q = (v.get("question") or "").strip() or "(no question)"
            a = (v.get("answer") or "").strip() or "(not provided)"
            qa_lines.append(f"**Q:** {q}\n**A:** {a}")
        core = "# Core Memory\n\n" + "\n\n".join(qa_lines)
        personal = "# Personal\n\n" + "\n\n".join(qa_lines)
        work_md = "# Work\n\n" + "\n\n".join(qa_lines)
        current_focus_md = "# Current Focus\n\n" + "\n\n".join(qa_lines)
        preferences_md = "# Preferences\n\n" + "\n\n".join(qa_lines)
        return {
            "core_memory": core.strip(),
            "personal": personal.strip(),
            "work": work_md.strip(),
            "current_focus": current_focus_md.strip(),
            "preferences": preferences_md.strip(),
        }

    name = answers.get("name", "(not provided)")
    work = answers.get("work", "(not provided)")
    location = answers.get("location", "(not provided)")
    current_focus = answers.get("current_focus", "(not provided)")
    interests = answers.get("interests", "(not provided)")
    communication_style = answers.get("communication_style", "(not provided)")

    core = f"""# Core Memory

**Name:** {name}
**Work:** {work}
**Location:** {location}

**Current focus:** {current_focus}
**Interests / topics for help:** {interests}
**Communication preferences:** {communication_style}
"""
    personal = f"""# Personal

- **Name:** {name}
- **Location:** {location}
"""
    work_md = f"""# Work

- **Role / status:** {work}
"""
    current_focus_md = f"""# Current Focus

- **Focus:** {current_focus}
- **Topics for help:** {interests}
"""
    preferences_md = f"""# Preferences

- **Communication:** {communication_style}
"""
    return {
        "core_memory": core.strip(),
        "personal": personal.strip(),
        "work": work_md.strip(),
        "current_focus": current_focus_md.strip(),
        "preferences": preferences_md.strip(),
    }


def generate_initial_memory(answers: dict) -> dict:
    """
    Takes user answers, sends to LLM, returns dict of memory content.
    On LLM failure: retry once, then fall back to template-based memory.
    """
    if _is_qa_format(answers):
        answers_formatted = "\n\n".join(
            f"**Q:** {v.get('question', '')}\n**A:** {v.get('answer', '')}"
            for v in answers.values()
        )
    else:
        answers_formatted = "\n".join(f"- **{k}:** {v}" for k, v in answers.items())
    prompt = MEMORY_GENERATION_PROMPT.format(answers_formatted=answers_formatted)

    messages = [
        {"role": "system", "content": "You output only valid JSON. No markdown, no explanation."},
        {"role": "user", "content": prompt},
    ]

    for attempt in range(2):
        response = call_llm(messages, tools=None, stream=False)
        if not response:
            continue
        content = (response.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        parsed = extract_json_from_response(content)
        if parsed and "core_memory" in parsed:
            result = {}
            for key in ("core_memory", "personal", "work", "current_focus", "preferences"):
                result[key] = (parsed.get(key) or "").strip() or "(empty)"
            return result

    console.print("[dim]LLM generation failed; using template-based memory.[/dim]")
    return _template_fallback_memory(answers)


def write_initial_memory(memory_content: dict) -> bool:
    """Write generated memory to AI Memory folder structure."""
    init_result = ensure_memory_structure()
    if not init_result.get("success"):
        console.print(f"[bold #FF10F0]Cannot write memory: {init_result.get('error', 'Unknown')}[/bold #FF10F0]")
        return False

    r1 = update_core_memory(memory_content.get("core_memory", ""))
    if not r1.get("success"):
        console.print(f"[bold #FF10F0]Failed to write core memory: {r1.get('error', 'Unknown')}[/bold #FF10F0]")
        return False

    for category, key in (
        ("personal", "personal"),
        ("work", "work"),
        ("current-focus", "current_focus"),
        ("preferences", "preferences"),
    ):
        r = update_context(category, memory_content.get(key, ""))
        if not r.get("success"):
            console.print(f"[bold #FF10F0]Failed to write {category}: {r.get('error', 'Unknown')}[/bold #FF10F0]")
            return False

    console.print("✓ Core memory created", style=STYLE_SUCCESS)
    console.print("✓ Personal context saved", style=STYLE_SUCCESS)
    console.print("✓ Work context saved", style=STYLE_SUCCESS)
    console.print("✓ Preferences saved", style=STYLE_SUCCESS)
    console.print("✓ Current focus documented", style=STYLE_SUCCESS)
    return True


def create_initial_memory_from_answers(answers: dict) -> bool:
    """Send answers to LLM to generate initial memory structure and write to disk."""
    memory_content = generate_initial_memory(answers)
    return write_initial_memory(memory_content)


def update_memory_from_answers(answers: dict, existing_memory: dict) -> bool:
    """Merge new Q&A answers with existing memory via LLM, then write updated memory."""
    existing_formatted = "\n\n".join(
        f"## {k}\n{v or '(empty)'}" for k, v in existing_memory.items()
    )
    answers_formatted = "\n\n".join(
        f"Q: {v.get('question', '')}\nA: {v.get('answer', '')}"
        for v in answers.values()
    )
    prompt = UPDATE_MEMORY_PROMPT.format(
        existing_memory_formatted=existing_formatted,
        answers_formatted=answers_formatted,
    )
    messages = [
        {"role": "system", "content": "You output only valid JSON. No markdown, no explanation."},
        {"role": "user", "content": prompt},
    ]

    for attempt in range(2):
        response = call_llm(messages, tools=None, stream=False)
        if not response:
            continue
        content = (response.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        parsed = extract_json_from_response(content)
        if not parsed or "core_memory" not in parsed:
            continue
        updated = {k: (parsed.get(k) or "").strip() for k in ("core_memory", "personal", "work", "current_focus", "preferences")}
        archived = (parsed.get("archived") or "").strip()

        init_result = ensure_memory_structure()
        if not init_result.get("success"):
            console.print(f"[bold #FF10F0]Cannot write memory: {init_result.get('error', 'Unknown')}[/bold #FF10F0]")
            return False

        r1 = update_core_memory(updated.get("core_memory", ""))
        if not r1.get("success"):
            console.print(f"[bold #FF10F0]Failed to write core memory: {r1.get('error', 'Unknown')}[/bold #FF10F0]")
            return False

        for category, key in (
            ("personal", "personal"),
            ("work", "work"),
            ("current-focus", "current_focus"),
            ("preferences", "preferences"),
        ):
            r = update_context(category, updated.get(key, ""))
            if not r.get("success"):
                console.print(f"[bold #FF10F0]Failed to write {category}: {r.get('error', 'Unknown')}[/bold #FF10F0]")
                return False

        if archived:
            archive_memory(archived)

        return True

    console.print("[bold #FF10F0]LLM failed to produce valid memory update; no changes written.[/bold #FF10F0]")
    return False


def run_memory_initialization() -> None:
    """Run adaptive Q&A for memory initialization or refresh."""
    memory_exists_flag = memory_exists()

    if memory_exists_flag:
        console.print("\n╭─ MEMORY REFRESH ─" + "─" * 50 + "╮", style="cyan")
        console.print("│ Reviewing what I know about you..." + " " * 28 + "│")
        console.print("╰─" + "─" * 63 + "╯\n")

        memory_content = load_all_memory()
        result = generate_questions(memory_exists_flag=True, memory_content=memory_content)

        if result.get("skip"):
            console.print(f"✓ {result.get('reason', 'Memory appears current.')}\n", style="green")
            try:
                skip = Prompt.ask("Skip refresh?", choices=["y", "n"], default="y")
            except (EOFError, KeyboardInterrupt):
                skip = "y"
            if skip == "y":
                return

        questions = result.get("questions", [])
    else:
        console.print("\n╭─ FIRST TIME SETUP ─" + "─" * 47 + "╮", style="cyan")
        console.print("│ Let me learn about you (takes ~2 minutes)" + " " * 22 + "│")
        console.print("╰─" + "─" * 63 + "╯\n")

        result = generate_questions(memory_exists_flag=False)
        questions = result.get("questions", [])

    answers = {}
    for i, question in enumerate(questions, 1):
        console.print(f"\n{i}. {question}", style="bold")
        try:
            answer = Prompt.ask(">")
        except (EOFError, KeyboardInterrupt):
            console.print("\nQ&A cancelled. No memory changes.")
            return
        answers[f"q{i}"] = {"question": question, "answer": answer or "(not provided)"}

    if memory_exists_flag:
        memory_content = load_all_memory()
        if not update_memory_from_answers(answers, memory_content):
            return
    else:
        if not create_initial_memory_from_answers(answers):
            return

    console.print("\n╭─ MEMORY UPDATED ─" + "─" * 49 + "╮", style="green")
    if memory_exists_flag:
        console.print("│ ✓ Memory refreshed with new information" + " " * 24 + "│")
    else:
        console.print("│ ✓ Core memory created" + " " * 42 + "│")
        console.print("│ ✓ Context files initialized" + " " * 36 + "│")
    console.print("╰─" + "─" * 63 + "╯\n")


def get_llm_response_simple(messages: list, system_message: str, extra_user_message: Optional[str] = None) -> Optional[str]:
    """Get a single LLM reply (no tools, no streaming). Used for exploratory conversation turns."""
    msgs = [{"role": "system", "content": system_message}]
    msgs.extend(messages)
    if extra_user_message:
        msgs.append({"role": "user", "content": extra_user_message})
    response = call_llm(msgs, tools=None, stream=False)
    if not response:
        return None
    return (response.get("choices") or [{}])[0].get("message", {}).get("content") or ""


def run_exploratory_conversation() -> list:
    """Conduct multi-turn exploratory conversation. Returns list of messages (role, content)."""
    console.print("\n╭─ EXPLORATORY CONVERSATION ─" + "─" * 40 + "╮")
    console.print("│ Let's have a real conversation so I can understand you.    │")
    console.print("│ Talk as much or as little as you want.                   │")
    console.print("│ Type 'done' when ready to wrap up.                         │")
    console.print("╰─" + "─" * 68 + "╯\n")

    conversation = []
    ai_opening = "So tell me about yourself - what's going on in your life right now?"
    console.print(f"\n{ai_opening}\n", style="cyan")
    conversation.append({"role": "assistant", "content": ai_opening})

    while True:
        try:
            user_input = Prompt.ask(">")
        except (EOFError, KeyboardInterrupt):
            break

        if user_input.lower().strip() == "done":
            farewell = get_llm_response_simple(
                conversation,
                EXPLORATION_PROMPT,
                extra_user_message="The user said they're done. Thank them and ask if there's anything else important before you wrap up.",
            )
            if farewell:
                console.print(f"\n{farewell}\n", style="cyan")
                conversation.append({"role": "assistant", "content": farewell})
            else:
                console.print("\nThanks for sharing all that. Anything else important before we wrap up?\n", style="cyan")
                conversation.append({"role": "assistant", "content": "Thanks for sharing all that. Anything else important before we wrap up?"})

            try:
                final_input = Prompt.ask(">")
            except (EOFError, KeyboardInterrupt):
                final_input = ""
            if final_input.lower().strip() not in ("no", "nope", "done", "nothing", ""):
                conversation.append({"role": "user", "content": final_input})
            break

        conversation.append({"role": "user", "content": user_input})
        response = get_llm_response_simple(conversation, EXPLORATION_PROMPT)
        if not response:
            response = "Tell me more about that."
        console.print(f"\n{response}\n", style="cyan")
        conversation.append({"role": "assistant", "content": response})

    return conversation


def extract_memory_from_conversation(conversation: list) -> Optional[dict]:
    """Send conversation to LLM for structured memory extraction. Returns parsed JSON dict or None."""
    prompt = build_exploration_extraction_prompt(conversation)
    messages = [
        {"role": "system", "content": "You output only valid JSON. No markdown code blocks, no explanation."},
        {"role": "user", "content": prompt},
    ]
    for attempt in range(2):
        response = call_llm(messages, tools=None, stream=False, max_tokens=8192)
        if not response:
            continue
        raw = (response.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        parsed = extract_json_from_response(raw)
        if not parsed:
            continue
        if "core_memory" in parsed:
            return parsed
    return None


def write_organized_memory(memory_structure: dict) -> bool:
    """Write extracted memory to disk and print success panel. Returns True on success."""
    result = memory_write_organized(memory_structure)
    if not result.get("success"):
        console.print(f"[bold #FF10F0]Failed to write memory: {result.get('error', 'Unknown')}[/bold #FF10F0]")
        return False

    created_context = [k for k, v in (memory_structure.get("context") or {}).items() if v]
    created_timelines = [k for k, v in (memory_structure.get("timelines") or {}).items() if v]

    console.print("\n╭─ MEMORY CREATED ─" + "─" * 50 + "╮", style="green")
    console.print("│ ✓ Core memory created" + " " * 45 + "│")
    n_ctx = len(created_context)
    console.print(f"│ ✓ Created {n_ctx} context files" + " " * max(0, 44 - len(str(n_ctx))) + "│")
    if created_timelines:
        n_tl = len(created_timelines)
        console.print(f"│ ✓ Created {n_tl} timeline files" + " " * max(0, 41 - len(str(n_tl))) + "│")
    console.print("╰─" + "─" * 68 + "╯\n")
    return True

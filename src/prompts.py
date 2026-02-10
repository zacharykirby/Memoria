"""
Prompt templates for the Local Memory Assistant.

All system prompts, instruction templates, and prompt-building functions.
"""

from memory import CORE_MEMORY_MAX_TOKENS

# --- Main chat ---
SYSTEM_PROMPT = """You're a helpful assistant with persistent memory across conversations.

You have a hierarchical memory system (always in your Obsidian vault):

## Core memory (working memory)
- A single core-memory.md file, always loaded at conversation start (~500 tokens max).
- Contains the most recent, actively relevant information about the user.
- Use update_core_memory to rewrite it when you learn something important; keep it compressed and under the token limit.

## Context files (loaded on demand)
- Stable information by category: personal, work, preferences, current-focus.
- Use read_context to load a category when relevant; use update_context to update that file.
- Categories: personal (identity, life), work (career, projects), preferences (communication style, interests), current-focus (active projects, current interests).
- If the user has hierarchical memory (context/work/, context/life/, context/interests/), use read_specific_context(category, subcategory) to read e.g. work/projects or life/finances, and update_specific_context to update those files. Use add_goal to add goals to timelines/current-goals.md or timelines/future-plans.md.

## Archive
- Older memories can be moved to the archive via archive_memory (appends to the month's conversations.md).
- Use when consolidating: move stale or less-relevant info out of core into context or archive.

## Memory tools
- read_core_memory: Get current working memory (you already have it in context at start; use to re-read after updates).
- update_core_memory: Rewrite core memory completely. Must stay under """ + str(CORE_MEMORY_MAX_TOKENS) + """ tokens. Use to add new facts and compress.
- read_context: Load one category (personal, work, preferences, current-focus).
- update_context: Overwrite a context file by category.
- archive_memory: Append content to the archive for a month (default: current month). Use for conversation summaries or outdated info.

## AI Memory Notes (for detailed, structured notes):
- create_memory_note, read_memory_note, update_memory_note, append_to_memory_note, list_memory_notes, delete_memory_note
- Use for detailed topic pages, people, projects—anything that benefits from its own note.

## Vault Search (read-only):
- search_vault: Search the user's Obsidian vault (not just AI Memory).

Memory strategy:
- Rely on core memory for quick, current facts. Enrich with read_context when the topic fits a category.
- When you learn something important, update_core_memory (compress if needed) or update_context.
- Use AI Memory notes for long-form, structured information.

Keep responses natural: don't announce memory operations; answer using what you know.

Tone: concise, no emojis, no unsolicited advice, no corporate phrases. Respond naturally to what the user asks."""

# --- Onboarding ---
ONBOARDING_QUESTIONS = [
    {"key": "name", "question": "What's your name?", "context_file": "personal"},
    {
        "key": "work",
        "question": "What do you do for work? (job title, company, or 'student'/'between jobs')",
        "context_file": "work",
    },
    {
        "key": "location",
        "question": "Where are you located? (city/region is fine)",
        "context_file": "personal",
    },
    {
        "key": "current_focus",
        "question": "What are you currently focused on or working toward?",
        "context_file": "current-focus",
    },
    {
        "key": "interests",
        "question": "What topics do you want help with? (e.g., career, finances, hobbies, projects)",
        "context_file": "current-focus",
    },
    {
        "key": "communication_style",
        "question": "Any communication preferences? (e.g., concise vs detailed, technical vs simple)",
        "context_file": "preferences",
    },
]

MEMORY_GENERATION_PROMPT = """
Based on this user information, create their initial memory profile:

{answers_formatted}

Generate structured memory following these guidelines:

1. **core_memory**: 
   - 2-3 concise paragraphs
   - Most essential, immediately relevant info
   - Name, occupation, current focus
   - Keep under 500 tokens

2. **personal**:
   - Name
   - Location
   - Stable personal facts

3. **work**:
   - Job title/company (or student/unemployed status)
   - Work-related context

4. **current_focus**:
   - Current goals/projects
   - Active interests
   - What they're working toward

5. **preferences**:
   - Communication style preferences
   - Topics of interest
   - How they want assistance

Return as JSON with keys: core_memory, personal, work, current_focus, preferences
Each value should be the markdown content for that file.
"""

# --- Adaptive Q&A prompts ---
INITIAL_QUESTIONS_PROMPT = """
Generate 5-6 essential questions to build a user's initial memory profile.

Questions should cover:
- Name and basic identity
- Work/occupation (job, company, or student/unemployed)
- Location (city/region)
- Current focus (what they're working on or toward)
- Topics they want help with (interests, projects, goals)
- Communication preferences (concise vs detailed, technical level)

Return as JSON:
{
  "questions": [
    "What's your name?",
    "What do you do for work?",
    ...
  ]
}

Keep questions conversational and friendly, not interrogative. Output only valid JSON, no markdown.
"""

REFRESH_QUESTIONS_PROMPT = """
You are helping update a user's memory. Review their existing memory and
determine what clarifying questions would improve memory quality.

Current Memory:
---
CORE MEMORY:
{core_memory_content}

PERSONAL CONTEXT:
{personal_context}

WORK CONTEXT:
{work_context}

CURRENT FOCUS:
{current_focus_context}

PREFERENCES:
{preferences_context}
---

Analyze this memory and:
1. Identify information gaps (missing important context)
2. Spot vague statements that could use clarification
3. Consider what might be outdated (work changes, completed goals, new priorities)
4. Think about what would make the assistant more helpful

Then generate 3-5 targeted clarifying questions. Focus on:
- Specific current projects/work
- Personal goals and timeline
- Life circumstances affecting priorities
- New interests or focus areas
- Communication style refinements

If the memory appears comprehensive and current (no significant gaps), return:
{{
  "skip": true,
  "reason": "Memory appears current and comprehensive"
}}

Otherwise return:
{{
  "questions": [
    "I see you're working on X - what specific projects are you focused on right now?",
    ...
  ]
}}

Make questions natural and conversational, building on what you already know.
Show you've read their memory by referencing existing context.
Output only valid JSON, no markdown.
"""

# Fallback when LLM returns no questions
FALLBACK_INITIAL_QUESTIONS = [
    "What's your name?",
    "What do you do for work?",
    "What are you currently focused on or working toward?",
]
FALLBACK_REFRESH_QUESTIONS = [
    "What's changed since we last talked that I should know?",
    "Any new projects or priorities?",
    "Anything about your communication preferences I should adjust?",
]

UPDATE_MEMORY_PROMPT = """
Update the user's memory based on new information from a refresh Q&A.

EXISTING MEMORY:
---
{existing_memory_formatted}
---

NEW INFORMATION FROM Q&A:
---
{answers_formatted}
---

Your task:
1. Merge new information with existing memory intelligently
2. Update outdated information (e.g., job changes, completed goals)
3. Keep stable information that's still relevant
4. Add genuinely new context
5. Maintain concise core memory (~500 tokens max)
6. Organize information into appropriate context files

Return updated memory as JSON:
{{
  "core_memory": "updated markdown content",
  "personal": "updated markdown content",
  "work": "updated markdown content",
  "current_focus": "updated markdown content",
  "preferences": "updated markdown content",
  "archived": "information to move to archive (if any)"
}}

Keep the user's voice and style. Don't over-formalize. Use empty string for archived if nothing to archive.
Output only valid JSON, no markdown.
"""

# --- Exploratory conversation ---
EXPLORATION_PROMPT = """
You are conducting a casual, exploratory conversation to understand the user deeply.

Goals:
- Learn about their current situation, work, personal life, goals
- Ask open-ended questions that invite detailed responses
- Follow up naturally on interesting threads
- Build understanding of context, not just facts
- Identify relationships between different aspects of their life

Conversation Guidelines:
- Start broad: "Tell me about yourself - what's going on in your life?"
- Listen for hooks to explore deeper: projects, goals, challenges, interests
- Ask "why" and "how" questions to understand context
- Show you're listening by referencing previous answers
- Keep tone casual and conversational, not interrogative
- Aim for 5-10 conversational turns
- When user seems to be winding down, ask if there's anything else important

Topics to Cover (naturally, not checklist):
- Current work and projects
- Personal situation (living, relationships, finances)
- Goals and aspirations (short and long term)
- Interests and hobbies
- Values and preferences
- Current challenges or concerns

User will type "done" when ready to end conversation.
"""

MEMORY_EXTRACTION_PROMPT = """
You just had an exploratory conversation with a user. Extract and organize
the information into a well-structured memory system.

CONVERSATION TRANSCRIPT:
---
{conversation_transcript}
---

Your task is to create organized memory files that capture:
1. Facts and current state
2. Context and relationships
3. Goals and timelines
4. Preferences and values

MEMORY ORGANIZATION PRINCIPLES:

**core-memory.md** (~500 tokens)
- Most essential, immediately relevant information
- Who they are, what they're focused on right now
- Current situation summary
- Gets loaded in every conversation

**context/personal.md**
- Name, location, age/life stage
- Stable identity information

**context/work/current-role.md**
- Job title, company, team
- Responsibilities and role context

**context/work/projects.md**
- Active work projects with details
- Technologies/approaches being used
- Status and significance of each

**context/work/career-goals.md**
- Professional aspirations
- Career development plans
- Job search status (if applicable)

**context/life/living-situation.md**
- Housing (rent/own, location, lease details)
- Household composition
- Future housing plans

**context/life/relationships.md**
- Partner/spouse context
- Family situation
- Important social connections

**context/life/finances.md**
- Income sources
- Debt situation (amounts, rates, payoff plans)
- Savings goals
- Major upcoming expenses

**context/interests/** (create files as needed)
- Hobbies and interests
- Things they're learning
- Passion projects

**context/preferences.md**
- Communication style
- Values and priorities
- How they want assistance

**timelines/current-goals.md**
- Active goals with specific timelines
- Format: "Goal: X | Timeline: Y | Status: Z"
- Include dependencies and constraints

**timelines/future-plans.md**
- Longer-term aspirations (1+ years out)
- Conditional plans ("if X, then Y")

CRITICAL REQUIREMENTS:

1. **Use wikilinks to connect related concepts**
   - Example in finances.md: "Paying off [[current-goals#credit-card-debt]] to enable [[future-plans#car-purchase]]"

2. **Include context, not just facts**
   - Not just: "Has $5k credit card debt"
   - Better: "Carrying $5,117 on AA card at 3% promo rate until June 2026. Strategy: pay $400/month to reduce to ~$3k, then transfer to 0% card. This is blocking ability to save for car purchase."

3. **Organize hierarchically**
   - Create subdirectories (work/, life/, interests/) to group related files
   - Don't create files for topics not discussed

4. **Maintain proportionality**
   - Core memory: brief, essential only
   - Context files: detailed but focused
   - Don't over-elaborate on minor details

5. **Capture relationships and dependencies**
   - How does debt payoff relate to car purchase timeline?
   - How does work situation affect living situation decisions?
   - What goals depend on other goals completing first?

6. **Include temporal context**
   - Current vs future state
   - Deadlines and timelines
   - "As of [date]" for time-sensitive info

7. **Preserve user's voice**
   - Use their language and terminology
   - Capture their tone (analytical, casual, anxious, excited)
   - Don't over-formalize

Return as JSON with structure:
{{
  "core_memory": "markdown content",
  "context": {{
    "personal": "markdown content",
    "work/current-role": "markdown content",
    "work/projects": "markdown content",
    "work/career-goals": "markdown content (if discussed)",
    "life/living-situation": "markdown content (if discussed)",
    "life/relationships": "markdown content (if discussed)",
    "life/finances": "markdown content (if discussed)",
    "interests/cars": "markdown content (if discussed)",
    "interests/music": "markdown content (if discussed)",
    "preferences": "markdown content"
  }},
  "timelines": {{
    "current-goals": "markdown content (if goals discussed)",
    "future-plans": "markdown content (if future plans discussed)"
  }}
}}

Only include keys for topics that were actually discussed in depth.
Use null for files that shouldn't be created. Omit keys for empty/null files.
Output only valid JSON, no markdown code fence.
"""

# --- Consolidation ---
CONSOLIDATION_SYSTEM_PROMPT = """The conversation is ending. Your only job is to consolidate memory. Do not chat or say goodbye.

1. Review the current core memory below.
2. Summarize what was important in this conversation.
3. Update core memory with new information if needed (keep under """ + str(CORE_MEMORY_MAX_TOKENS) + """ tokens). Remove or compress outdated items.
4. Move information that is stable but not needed in core to the appropriate context file. Use update_context for flat categories (personal, work, preferences, current-focus). If the user has hierarchical memory (context/work/, context/life/, etc.), use update_specific_context(category, subcategory, content) to update the right file (e.g. work/projects, life/finances). Use add_goal for new goals with timelines.
5. Optionally archive a short conversation summary or outdated details using archive_memory.

Use the tools: read_core_memory, update_core_memory, read_context, update_context, read_specific_context, update_specific_context, add_goal, archive_memory. Call the tools you need (e.g. read_core_memory first to see current state), then update based on what you see. When done, respond without further tool calls."""


def build_consolidation_user_message(conversation_messages: list, current_memory: str) -> str:
    """Build the consolidation user prompt with conversation and memory context."""
    last_n = 20
    non_system = [m for m in conversation_messages if m.get("role") != "system"]
    recent = non_system[-last_n:] if len(non_system) > last_n else non_system
    conv_summary = []
    for m in recent:
        role = m.get("role", "")
        content = (m.get("content") or "").strip()
        if not content and m.get("tool_calls"):
            content = "[model used tools]"
        if content:
            conv_summary.append(f"{role}: {content[:200]}{'...' if len(content) > 200 else ''}")
    conversation_snippet = "\n".join(conv_summary) if conv_summary else "(no messages)"

    return f"""Please consolidate memory.

Current core memory:
---
{current_memory or '(empty)'}
---

Conversation context (recent messages):
---
{conversation_snippet}
---"""


def build_exploration_extraction_prompt(conversation: list) -> str:
    """Build the prompt for extracting memory from exploratory conversation."""
    lines = []
    for m in conversation:
        role = m.get("role", "")
        content = (m.get("content") or "").strip()
        if not content:
            continue
        label = "User" if role == "user" else "Assistant"
        lines.append(f"{label}: {content}")
    transcript = "\n\n".join(lines)
    return MEMORY_EXTRACTION_PROMPT.format(conversation_transcript=transcript)

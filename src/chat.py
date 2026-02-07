# chat.py
import json
import requests
import sys
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from memory import save_fact, retrieve_facts
from obsidian import (
    search_vault,
    create_memory_note,
    read_memory_note,
    update_memory_note,
    append_to_memory_note,
    list_memory_notes,
    delete_memory_note
)
import os
from dotenv import load_dotenv

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text
from rich.live import Live
from rich.style import Style
from rich.theme import Theme

load_dotenv()
URL = os.getenv("LMSTUDIO_URL", "http://localhost:1234")

LM_STUDIO_URL = f"{URL}/v1/chat/completions"

# Cyberpunk color scheme
CYBER_THEME = Theme({
    "cyan": "#00D9FF",
    "magenta": "#FF10F0",
    "neon_green": "#39FF14",
    "dim_cyan": "dim #00D9FF",
    "bright_white": "bright_white",
})

console = Console(theme=CYBER_THEME)

# Styles
STYLE_TOOL_CALL = Style(color="#00D9FF", bold=True)
STYLE_TOOL_RESULT = Style(color="#FF10F0")
STYLE_THINKING = Style(color="#00D9FF", dim=True)
STYLE_SUCCESS = Style(color="#39FF14")
STYLE_ERROR = Style(color="#FF10F0", bold=True)
STYLE_PROMPT = Style(color="#00D9FF", bold=True)

SYSTEM_PROMPT = """You're a helpful assistant with persistent memory across conversations.

You have access to multiple tools organized into categories:

## Basic Memory (for simple facts):
- retrieve_facts: Search your memory for information about the user. Use with no query (or empty string) to get ALL facts.
- store_fact: Save new information about the user for future conversations. Store facts as single, atomic statements (one fact per call).

## AI Memory Notes (for detailed information):
- create_memory_note: Create structured notes in AI Memory/ folder for detailed information
- read_memory_note: Read existing memory notes
- update_memory_note: Replace entire content of a memory note
- append_to_memory_note: Add content to end of existing memory note
- list_memory_notes: List all memory notes (optionally in a subfolder)
- delete_memory_note: Delete a memory note (use sparingly)

## Vault Search (read-only):
- search_vault: Search the user's Obsidian vault for existing notes

When to use basic memory (store_fact/retrieve_facts):
- Simple, atomic facts (name, preferences, single statements)
- Quick lookups of basic information
- Information that doesn't need structure or organization

When to use AI Memory Notes:
- Detailed, structured information that needs organization
- Information about complex topics (projects, people, conversations)
- Content that needs to be updated over time (e.g., ongoing projects)
- Information that benefits from categorization (use subfolders like 'topics/', 'people/')
- When you want to maintain comprehensive notes that grow over time

Example AI Memory structure:
- user.md - Overall information about the user
- topics/cars.md - Detailed notes about user's interest in cars
- topics/work.md - Work-related information
- people/john.md - Notes about people the user mentions

When to use search_vault:
- When the user wants to find notes in their existing Obsidian vault (not AI Memory)
- Searching their personal knowledge base, documentation, or notes
- Use tags parameter to filter by specific topics
- Use folder parameter to limit search to specific folders

Memory strategy:
- Start with list_memory_notes to see what you already have
- Create organized notes for topics that come up in conversation
- Update existing notes as you learn more
- Use descriptive filenames and organize with subfolders
- Add topic tags for easy categorization

Keep responses natural:
- Don't announce when you're checking memory or explain the memory system
- Don't be overly eager or use excessive formatting
- Just answer naturally using the information you find

Tone guidelines:
- Keep responses concise and natural
- Don't use emojis in conversational responses
- Don't make assumptions or offer unsolicited advice
- Avoid corporate-assistant phrases like "How can I assist you today?"
- Just respond naturally to what the user actually asks"""

STORE_FACT_TOOL = {
    "type": "function",
    "function": {
        "name": "store_fact",
        "description": "Store a new fact about the user for future conversations",
        "parameters": {
            "type": "object",
            "properties": {
                "fact": {
                    "type": "string",
                    "description": "The fact to remember about the user"
                }
            },
            "required": ["fact"]
        }
    }
}

RETRIEVE_FACTS_TOOL = {
    "type": "function",
    "function": {
        "name": "retrieve_facts",
        "description": "Retrieve facts about the user from memory. Can optionally filter by a search query.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Optional search query to filter facts (e.g., 'hobbies', 'job', 'family')"
                }
            },
            "required": []
        }
    }
}

SEARCH_VAULT_TOOL = {
    "type": "function",
    "function": {
        "name": "search_vault",
        "description": "Search the user's Obsidian vault for notes matching a query. Searches both note titles and content.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Text to search for in note titles and content"
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of tags to filter by (e.g., ['project', 'work'])"
                },
                "folder": {
                    "type": "string",
                    "description": "Optional folder path to limit search (e.g., 'Work/Projects')"
                }
            },
            "required": ["query"]
        }
    }
}

CREATE_MEMORY_NOTE_TOOL = {
    "type": "function",
    "function": {
        "name": "create_memory_note",
        "description": "Create a new note in the AI Memory/ folder to store information for future reference",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Note title (will be the filename)"
                },
                "content": {
                    "type": "string",
                    "description": "Note content in markdown format"
                },
                "subfolder": {
                    "type": "string",
                    "description": "Optional subfolder within AI Memory (e.g., 'topics' or 'people')"
                },
                "topics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional topic tags for categorization"
                }
            },
            "required": ["title", "content"]
        }
    }
}

READ_MEMORY_NOTE_TOOL = {
    "type": "function",
    "function": {
        "name": "read_memory_note",
        "description": "Read an existing note from the AI Memory/ folder",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Filename relative to AI Memory/ folder (e.g., 'user.md' or 'topics/cars.md')"
                }
            },
            "required": ["filename"]
        }
    }
}

UPDATE_MEMORY_NOTE_TOOL = {
    "type": "function",
    "function": {
        "name": "update_memory_note",
        "description": "Replace the entire content of an existing memory note",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Filename relative to AI Memory/ folder"
                },
                "new_content": {
                    "type": "string",
                    "description": "New content for the note (markdown)"
                },
                "topics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional updated topic tags"
                }
            },
            "required": ["filename", "new_content"]
        }
    }
}

APPEND_TO_MEMORY_NOTE_TOOL = {
    "type": "function",
    "function": {
        "name": "append_to_memory_note",
        "description": "Add content to the end of an existing memory note",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Filename relative to AI Memory/ folder"
                },
                "content": {
                    "type": "string",
                    "description": "Content to append (markdown)"
                }
            },
            "required": ["filename", "content"]
        }
    }
}

LIST_MEMORY_NOTES_TOOL = {
    "type": "function",
    "function": {
        "name": "list_memory_notes",
        "description": "List all notes in the AI Memory/ folder",
        "parameters": {
            "type": "object",
            "properties": {
                "subfolder": {
                    "type": "string",
                    "description": "Optional subfolder to list (e.g., 'topics')"
                }
            },
            "required": []
        }
    }
}

DELETE_MEMORY_NOTE_TOOL = {
    "type": "function",
    "function": {
        "name": "delete_memory_note",
        "description": "Delete a memory note (use sparingly, only when explicitly requested or content is clearly wrong)",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Filename relative to AI Memory/ folder"
                }
            },
            "required": ["filename"]
        }
    }
}


class StreamingResponse:
    """Handles streaming response display with rich Live"""

    def __init__(self):
        self.content = ""
        self.tool_calls_accumulated = []

    def update(self, new_content: str):
        self.content += new_content

    def get_display(self) -> Markdown:
        return Markdown(self.content) if self.content else Text("")


def call_llm(messages, tools=None, stream=False, live_display=None):
    """Call LM Studio API, optionally with streaming"""
    payload = {
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 500,
        "stream": stream
    }

    if tools:
        payload["tools"] = tools

    try:
        if not stream:
            response = requests.post(LM_STUDIO_URL, json=payload)
            response.raise_for_status()
            return response.json()

        # Streaming mode
        response = requests.post(LM_STUDIO_URL, json=payload, stream=True)
        response.raise_for_status()

        full_content = ""
        tool_calls_accumulated = []

        for line in response.iter_lines():
            if not line:
                continue

            line_text = line.decode('utf-8')
            if not line_text.startswith("data: "):
                continue

            data = line_text[6:]  # Remove "data: " prefix

            if data == "[DONE]":
                break

            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue

            delta = chunk["choices"][0].get("delta", {})

            # Stream content tokens
            content = delta.get("content")
            if content:
                full_content += content
                if live_display:
                    live_display.update(Markdown(full_content))

            # Accumulate tool calls (they come in pieces)
            if "tool_calls" in delta:
                for tc in delta["tool_calls"]:
                    idx = tc.get("index", 0)
                    while len(tool_calls_accumulated) <= idx:
                        tool_calls_accumulated.append({
                            "id": "",
                            "type": "function",
                            "function": {"name": "", "arguments": ""}
                        })
                    if "id" in tc:
                        tool_calls_accumulated[idx]["id"] = tc["id"]
                    if "function" in tc:
                        func = tc["function"]
                        if "name" in func:
                            tool_calls_accumulated[idx]["function"]["name"] += func["name"]
                        if "arguments" in func:
                            tool_calls_accumulated[idx]["function"]["arguments"] += func["arguments"]

        # Return in format compatible with existing code
        message = {"content": full_content if full_content else None}
        if tool_calls_accumulated:
            message["tool_calls"] = tool_calls_accumulated

        return {"choices": [{"message": message}]}

    except requests.exceptions.RequestException as e:
        console.print(f"[bold magenta]Error calling LLM:[/bold magenta] {e}")
        return None


def execute_tool(func_name, args):
    """Execute a tool call and return the result"""
    if func_name == "store_fact":
        fact = args.get("fact")
        if fact:
            if save_fact(fact):
                return f"Successfully stored: {fact}"
            else:
                return f"Already knew: {fact}"
        return "Error: No fact provided"

    elif func_name == "retrieve_facts":
        query = args.get("query")
        facts = retrieve_facts(query)
        if facts:
            facts_list = "\n".join(f"- {fact}" for fact in facts)
            if query and query.strip():
                return f"Found {len(facts)} fact(s) matching '{query}':\n{facts_list}"
            else:
                return f"Found {len(facts)} fact(s) total:\n{facts_list}"
        else:
            if query and query.strip():
                return f"No facts found matching '{query}'"
            else:
                return "No facts stored yet"

    elif func_name == "search_vault":
        query = args.get("query")
        tags = args.get("tags")
        folder = args.get("folder")

        if not query:
            return "Error: No search query provided"

        result = search_vault(query, tags=tags, folder=folder)

        # Handle errors
        if "error" in result:
            return f"Error: {result['error']}"

        # Format results
        results = result.get("results", [])
        total_found = result.get("total_found", len(results))

        if not results:
            filter_info = ""
            if tags:
                filter_info += f" with tags {tags}"
            if folder:
                filter_info += f" in folder '{folder}'"
            return f"No notes found matching '{query}'{filter_info}"

        # Build formatted response
        response_lines = [f"Found {total_found} note(s) matching '{query}':"]

        for i, note in enumerate(results, 1):
            response_lines.append(f"\n{i}. **{note['title']}**")
            response_lines.append(f"   Path: {note['filepath']}")
            if note.get('tags'):
                response_lines.append(f"   Tags: {', '.join(note['tags'])}")
            response_lines.append(f"   Preview: {note['preview']}")

        if total_found > len(results):
            response_lines.append(f"\n(Showing top {len(results)} of {total_found} results)")

        return "\n".join(response_lines)

    elif func_name == "create_memory_note":
        title = args.get("title")
        content = args.get("content")
        subfolder = args.get("subfolder")
        topics = args.get("topics")

        if not title or not content:
            return "Error: Both title and content are required"

        result = create_memory_note(title, content, subfolder=subfolder, topics=topics)

        if result.get("success"):
            return result["message"]
        else:
            return f"Error: {result['error']}"

    elif func_name == "read_memory_note":
        filename = args.get("filename")

        if not filename:
            return "Error: filename is required"

        result = read_memory_note(filename)

        if result.get("success"):
            response = f"**{result['filepath']}**\n\n"
            if result.get("metadata"):
                metadata = result["metadata"]
                if metadata.get("created"):
                    response += f"Created: {metadata['created']}\n"
                if metadata.get("updated"):
                    response += f"Updated: {metadata['updated']}\n"
                if metadata.get("topics"):
                    response += f"Topics: {', '.join(metadata['topics'])}\n"
                response += "\n"
            response += result["content"]
            return response
        else:
            return f"Error: {result['error']}"

    elif func_name == "update_memory_note":
        filename = args.get("filename")
        new_content = args.get("new_content")
        topics = args.get("topics")

        if not filename or not new_content:
            return "Error: filename and new_content are required"

        result = update_memory_note(filename, new_content, topics=topics)

        if result.get("success"):
            return result["message"]
        else:
            return f"Error: {result['error']}"

    elif func_name == "append_to_memory_note":
        filename = args.get("filename")
        content = args.get("content")

        if not filename or not content:
            return "Error: filename and content are required"

        result = append_to_memory_note(filename, content)

        if result.get("success"):
            return result["message"]
        else:
            return f"Error: {result['error']}"

    elif func_name == "list_memory_notes":
        subfolder = args.get("subfolder")

        result = list_memory_notes(subfolder=subfolder)

        if result.get("success"):
            notes = result.get("notes", [])
            if not notes:
                return result.get("message", "No memory notes found")

            response_lines = [f"Found {result['count']} memory note(s):"]
            for note in notes:
                response_lines.append(f"\n- **{note['filepath']}**")
                if note.get("topics"):
                    response_lines.append(f"  Topics: {', '.join(note['topics'])}")
                if note.get("updated"):
                    response_lines.append(f"  Updated: {note['updated']}")

            return "\n".join(response_lines)
        else:
            return f"Error: {result['error']}"

    elif func_name == "delete_memory_note":
        filename = args.get("filename")

        if not filename:
            return "Error: filename is required"

        result = delete_memory_note(filename)

        if result.get("success"):
            return result["message"]
        else:
            return f"Error: {result['error']}"

    return f"Unknown tool: {func_name}"


def display_tool_call(func_name: str, args: dict):
    """Display a tool call in a cyan panel"""
    if args:
        args_display = ", ".join(f'{k}="{v}"' for k, v in args.items() if v)
        if args_display:
            call_text = f"{func_name}({args_display})"
        else:
            call_text = f"{func_name}()"
    else:
        call_text = f"{func_name}()"

    panel = Panel(
        Text(call_text, style=STYLE_TOOL_CALL),
        title="[bold #00D9FF]TOOL CALL[/bold #00D9FF]",
        title_align="left",
        border_style="#00D9FF",
        padding=(0, 1),
    )
    console.print(panel)


def display_tool_result(result: str):
    """Display a tool result in a magenta panel"""
    result_preview = result[:200] + "..." if len(result) > 200 else result

    panel = Panel(
        Text(result_preview, style=STYLE_TOOL_RESULT),
        title="[bold #FF10F0]RESULT[/bold #FF10F0]",
        title_align="left",
        border_style="#FF10F0",
        padding=(0, 1),
    )
    console.print(panel)


def display_thinking():
    """Display thinking indicator"""
    text = Text("processing...", style=STYLE_THINKING)
    console.print(text)


def display_welcome():
    """Display welcome message with cyberpunk styling"""
    title = Text()
    title.append("LOCAL MEMORY ASSISTANT", style="bold #00D9FF")

    subtitle = Text()
    subtitle.append("Type ", style="dim white")
    subtitle.append("quit", style="#FF10F0")
    subtitle.append(" to exit", style="dim white")

    panel = Panel(
        Text.assemble(title, "\n", subtitle),
        border_style="#00D9FF",
        padding=(0, 2),
    )
    console.print(panel)
    console.print()


def get_user_input() -> str:
    """Get user input with styled prompt"""
    console.print()
    prompt = Text()
    prompt.append("> ", style="bold #00D9FF")
    console.print(prompt, end="")
    return input().strip()


def display_response(content: str):
    """Display assistant response as rendered markdown"""
    if content:
        console.print()
        console.print(Markdown(content))


def main():
    display_welcome()

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    tools = [
        STORE_FACT_TOOL,
        RETRIEVE_FACTS_TOOL,
        SEARCH_VAULT_TOOL,
        CREATE_MEMORY_NOTE_TOOL,
        READ_MEMORY_NOTE_TOOL,
        UPDATE_MEMORY_NOTE_TOOL,
        APPEND_TO_MEMORY_NOTE_TOOL,
        LIST_MEMORY_NOTES_TOOL,
        DELETE_MEMORY_NOTE_TOOL
    ]

    while True:
        user_input = get_user_input()

        if user_input.lower() in ['quit', 'exit']:
            console.print()
            goodbye = Text("Goodbye!", style="bold #FF10F0")
            console.print(goodbye)
            break

        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})

        # Agentic loop - continue until model stops calling tools
        iteration = 0
        while True:
            iteration += 1

            # Only stream on the first iteration (to show thinking in real-time)
            use_streaming = (iteration == 1)

            if iteration == 1:
                console.print()
                # Use Live for streaming response
                with Live(Markdown(""), console=console, refresh_per_second=15, transient=False) as live:
                    response = call_llm(messages, tools=tools, stream=use_streaming, live_display=live)
            else:
                response = call_llm(messages, tools=tools, stream=False)

            if not response:
                console.print("[bold #FF10F0]Failed to get response from LLM[/bold #FF10F0]")
                break

            message = response["choices"][0]["message"]
            tool_calls_raw = message.get("tool_calls")

            # If there are tool calls, execute them and loop
            if tool_calls_raw:
                # Add assistant message with tool calls to history
                messages.append({
                    "role": "assistant",
                    "content": message.get("content"),
                    "tool_calls": tool_calls_raw
                })

                # Execute each tool and add results to history
                for i, tool_call in enumerate(tool_calls_raw):
                    func_name = tool_call["function"]["name"]
                    args_raw = tool_call["function"]["arguments"]
                    tool_call_id = tool_call.get("id", f"call_{i}")

                    # Parse arguments
                    try:
                        args = json.loads(args_raw)
                    except json.JSONDecodeError:
                        args = {}

                    console.print()
                    display_tool_call(func_name, args)

                    # Execute tool
                    result = execute_tool(func_name, args)

                    display_tool_result(result)

                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "name": func_name,
                        "content": result
                    })

                # Model will think again with the tool results
                console.print()
                display_thinking()

            else:
                # No tool calls - this is the final response
                if iteration > 1:
                    # Stream the final response
                    console.print()
                    with Live(Markdown(""), console=console, refresh_per_second=15, transient=False) as live:
                        response = call_llm(messages, tools=tools, stream=True, live_display=live)
                    if response:
                        message = response["choices"][0]["message"]

                # Add final assistant response to message history
                assistant_text = message.get("content", "")
                if assistant_text:
                    messages.append({"role": "assistant", "content": assistant_text})

                break  # Exit agentic loop


if __name__ == "__main__":
    main()

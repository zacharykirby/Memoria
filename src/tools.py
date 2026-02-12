"""
Tool definitions and execution for the Local Memory Assistant.

Defines all available tools (search, memory operations, etc.) and handles
tool execution dispatch.
"""

import json
from memory import (
    read_core_memory,
    update_core_memory,
    read_context,
    update_context,
    archive_memory,
    read_specific_context,
    update_specific_context,
    add_goal as memory_add_goal,
    CONTEXT_CATEGORIES,
    CORE_MEMORY_MAX_TOKENS,
)
from obsidian import (
    search_vault,
    create_memory_note,
    read_memory_note,
    update_memory_note,
    append_to_memory_note,
    list_memory_notes,
    delete_memory_note,
)

# --- Tool definitions ---
READ_CORE_MEMORY_TOOL = {
    "type": "function",
    "function": {
        "name": "read_core_memory",
        "description": "Read current core working memory (core-memory.md). Call this at the start of any response that touches on personal topics, preferences, ongoing work, or anything the user might expect you to already know. Also use to re-read after updates.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }
}

UPDATE_CORE_MEMORY_TOOL = {
    "type": "function",
    "function": {
        "name": "update_core_memory",
        "description": "Rewrite core working memory. Content must be under " + str(CORE_MEMORY_MAX_TOKENS) + " tokens. Call this after any response where you learned something new and important about the user - don't wait to be asked. Keep only the most relevant facts; compress to stay under the limit.",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Full new content for core-memory.md (markdown). Must be under " + str(CORE_MEMORY_MAX_TOKENS) + " tokens."},
            },
            "required": ["content"],
        },
    }
}

READ_CONTEXT_TOOL = {
    "type": "function",
    "function": {
        "name": "read_context",
        "description": "Read a context file by category. Call this when the user asks about work, personal life, preferences, or current projects and core memory doesn't have enough detail.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "One of: personal, work, preferences, current-focus",
                    "enum": list(CONTEXT_CATEGORIES),
                },
            },
            "required": ["category"],
        },
    }
}

UPDATE_CONTEXT_TOOL = {
    "type": "function",
    "function": {
        "name": "update_context",
        "description": "Update a context file by category. Overwrites the file.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "One of: personal, work, preferences, current-focus",
                    "enum": list(CONTEXT_CATEGORIES),
                },
                "content": {"type": "string", "description": "New content for the context file (markdown)."},
            },
            "required": ["category", "content"],
        },
    }
}

ARCHIVE_MEMORY_TOOL = {
    "type": "function",
    "function": {
        "name": "archive_memory",
        "description": "Append content to the archive for a given month. Use for conversation summaries or moving outdated info out of core.",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Content to archive (e.g. conversation summary)."},
                "date": {"type": "string", "description": "Optional. YYYY-MM; default is current month."},
            },
            "required": ["content"],
        },
    }
}

SEARCH_VAULT_TOOL = {
    "type": "function",
    "function": {
        "name": "search_vault",
        "description": "Search the user's Obsidian vault for notes matching a query. Call this when the user references a note, document, or topic that might exist in their vault, or asks you to find something. Searches both note titles and content.",
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

READ_SPECIFIC_CONTEXT_TOOL = {
    "type": "function",
    "function": {
        "name": "read_specific_context",
        "description": "Read a specific context file or all files in a category. Use instead of read_context when you know the specific subcategory needed (e.g. work/projects, life/finances). For hierarchical memory (context/work/, context/life/, context/interests/).",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Category: work, life, interests, personal, preferences",
                },
                "subcategory": {
                    "type": "string",
                    "description": "Specific file (e.g. projects, finances, current-role). Omit to read all files in category.",
                },
            },
            "required": ["category"],
        },
    }
}

UPDATE_SPECIFIC_CONTEXT_TOOL = {
    "type": "function",
    "function": {
        "name": "update_specific_context",
        "description": "Update a specific context file (e.g. work/projects, life/finances). Creates file if needed.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Category: work, life, interests, etc."},
                "subcategory": {"type": "string", "description": "File name: projects, finances, current-role, etc."},
                "content": {"type": "string", "description": "New markdown content for the file"},
            },
            "required": ["category", "subcategory", "content"],
        },
    }
}

ADD_GOAL_TOOL = {
    "type": "function",
    "function": {
        "name": "add_goal",
        "description": "Add a goal to timeline (current-goals.md or future-plans.md).",
        "parameters": {
            "type": "object",
            "properties": {
                "goal_description": {"type": "string", "description": "Description of the goal"},
                "timeline": {"type": "string", "description": "Timeline or deadline (e.g. 'by June 2026', '1-2 years')"},
                "goal_type": {
                    "type": "string",
                    "description": "current (active goals) or future (longer-term)",
                    "enum": ["current", "future"],
                },
            },
            "required": ["goal_description", "timeline"],
        },
    }
}

# Tool lists for different contexts
CHAT_TOOLS = [
    READ_CORE_MEMORY_TOOL,
    UPDATE_CORE_MEMORY_TOOL,
    READ_CONTEXT_TOOL,
    UPDATE_CONTEXT_TOOL,
    ARCHIVE_MEMORY_TOOL,
    READ_SPECIFIC_CONTEXT_TOOL,
    UPDATE_SPECIFIC_CONTEXT_TOOL,
    ADD_GOAL_TOOL,
    SEARCH_VAULT_TOOL,
    CREATE_MEMORY_NOTE_TOOL,
    READ_MEMORY_NOTE_TOOL,
    UPDATE_MEMORY_NOTE_TOOL,
    APPEND_TO_MEMORY_NOTE_TOOL,
    LIST_MEMORY_NOTES_TOOL,
    DELETE_MEMORY_NOTE_TOOL,
]

CONSOLIDATION_TOOLS = [
    READ_CORE_MEMORY_TOOL,
    UPDATE_CORE_MEMORY_TOOL,
    READ_CONTEXT_TOOL,
    UPDATE_CONTEXT_TOOL,
    READ_SPECIFIC_CONTEXT_TOOL,
    UPDATE_SPECIFIC_CONTEXT_TOOL,
    ADD_GOAL_TOOL,
    ARCHIVE_MEMORY_TOOL,
]


def parse_tool_arguments(tool_call: dict) -> dict:
    """Parse tool call arguments; handle both JSON string and already-parsed dict."""
    func = tool_call.get("function") or {}
    raw = func.get("arguments", func.get("parameters", "{}"))
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return {}


def _handle_read_core_memory(args):
    content = read_core_memory()
    return content if content else "(Core memory is empty.)"


def _handle_update_core_memory(args):
    content = args.get("content")
    content = str(content) if content is not None else ""
    result = update_core_memory(content)
    if result.get("success"):
        return f"Core memory updated ({result.get('tokens', 0)} tokens)."
    return f"Error: {result.get('error', 'Unknown error')}"


def _handle_read_context(args):
    category = args.get("category", "")
    content = read_context(category)
    if content:
        return f"**context/{category}.md**\n\n{content}"
    if category not in CONTEXT_CATEGORIES:
        return f"Error: Invalid category. Use one of: {', '.join(CONTEXT_CATEGORIES)}"
    return f"(Context '{category}' is empty.)"


def _handle_update_context(args):
    category = args.get("category", "")
    content = args.get("content", "")
    result = update_context(category, content)
    if result.get("success"):
        return f"Updated {result.get('filepath', 'context/' + category + '.md')}."
    return f"Error: {result.get('error', 'Unknown error')}"


def _handle_archive_memory(args):
    content = args.get("content", "")
    date = args.get("date")
    result = archive_memory(content, date=date)
    if result.get("success"):
        return f"Archived to {result.get('filepath', 'archive')}."
    return f"Error: {result.get('error', 'Unknown error')}"


def _handle_search_vault(args):
    query = args.get("query")
    tags = args.get("tags")
    folder = args.get("folder")

    if not query:
        return "Error: No search query provided"

    result = search_vault(query, tags=tags, folder=folder)

    if "error" in result:
        return f"Error: {result['error']}"

    results = result.get("results", [])
    total_found = result.get("total_found", len(results))

    if not results:
        filter_info = ""
        if tags:
            filter_info += f" with tags {tags}"
        if folder:
            filter_info += f" in folder '{folder}'"
        return f"No notes found matching '{query}'{filter_info}"

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


def _handle_create_memory_note(args):
    title = args.get("title")
    content = args.get("content")
    subfolder = args.get("subfolder")
    topics = args.get("topics")

    if not title or not content:
        return "Error: Both title and content are required"

    result = create_memory_note(title, content, subfolder=subfolder, topics=topics)
    if result.get("success"):
        return result["message"]
    return f"Error: {result['error']}"


def _handle_read_memory_note(args):
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
    return f"Error: {result['error']}"


def _handle_update_memory_note(args):
    filename = args.get("filename")
    new_content = args.get("new_content")
    topics = args.get("topics")

    if not filename or not new_content:
        return "Error: filename and new_content are required"

    result = update_memory_note(filename, new_content, topics=topics)
    if result.get("success"):
        return result["message"]
    return f"Error: {result['error']}"


def _handle_append_to_memory_note(args):
    filename = args.get("filename")
    content = args.get("content")
    if not filename or not content:
        return "Error: filename and content are required"

    result = append_to_memory_note(filename, content)
    if result.get("success"):
        return result["message"]
    return f"Error: {result['error']}"


def _handle_list_memory_notes(args):
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
    return f"Error: {result['error']}"


def _handle_delete_memory_note(args):
    filename = args.get("filename")
    if not filename:
        return "Error: filename is required"

    result = delete_memory_note(filename)
    if result.get("success"):
        return result["message"]
    return f"Error: {result['error']}"


def _handle_read_specific_context(args):
    category = args.get("category", "")
    subcategory = args.get("subcategory")
    content = read_specific_context(category, subcategory)
    if content:
        label = f"context/{category}" + (f"/{subcategory}" if subcategory else "") + ".md"
        return f"**{label}**\n\n{content}"
    return f"(No content for context/{category}" + (f"/{subcategory}" if subcategory else "") + ")"


def _handle_update_specific_context(args):
    category = args.get("category", "")
    subcategory = args.get("subcategory", "")
    content = args.get("content", "")
    result = update_specific_context(category, subcategory, content)
    if result.get("success"):
        return f"Updated {result.get('filepath', 'context file')}."
    return f"Error: {result.get('error', 'Unknown error')}"


def _handle_add_goal(args):
    goal_description = args.get("goal_description", "")
    timeline = args.get("timeline", "")
    goal_type = args.get("goal_type", "current")
    result = memory_add_goal(goal_description, timeline, goal_type=goal_type)
    if result.get("success"):
        return f"Goal added to {result.get('filepath', 'timeline')}."
    return f"Error: {result.get('error', 'Unknown error')}"


_TOOL_DISPATCH = {
    "read_core_memory": _handle_read_core_memory,
    "update_core_memory": _handle_update_core_memory,
    "read_context": _handle_read_context,
    "update_context": _handle_update_context,
    "archive_memory": _handle_archive_memory,
    "search_vault": _handle_search_vault,
    "create_memory_note": _handle_create_memory_note,
    "read_memory_note": _handle_read_memory_note,
    "update_memory_note": _handle_update_memory_note,
    "append_to_memory_note": _handle_append_to_memory_note,
    "list_memory_notes": _handle_list_memory_notes,
    "delete_memory_note": _handle_delete_memory_note,
    "read_specific_context": _handle_read_specific_context,
    "update_specific_context": _handle_update_specific_context,
    "add_goal": _handle_add_goal,
}


def execute_tool(func_name, args):
    """Execute a tool call and return the result."""
    handler = _TOOL_DISPATCH.get(func_name)
    if handler:
        return handler(args)
    return f"Unknown tool: {func_name}"

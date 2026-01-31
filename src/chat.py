# chat.py
import json
import requests
from memory import load_facts, save_fact

LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"

SYSTEM_PROMPT = """You are a helpful assistant with memory.

What you know about the user:
{facts}

You can store new facts about the user by calling the store_fact function.
Only store NEW facts that aren't already in your knowledge base.
Store facts as single, atomic statements (one fact per call).
Don't combine multiple facts into one statement."""

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

def call_llm(messages, tools=None, stream=False):
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

            # Stream content tokens to stdout
            content = delta.get("content")
            if content:
                print(content, end='', flush=True)
                full_content += content

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
        print(f"Error calling LLM: {e}")
        return None

def main():
    print("Local Memory Assistant - Type 'quit' to exit\n")
    
    # Load existing facts
    facts = load_facts()
    
    # Build system message with facts
    facts_text = "\n".join(f"- {fact}" for fact in facts) if facts else "None yet"
    system_msg = SYSTEM_PROMPT.format(facts=facts_text)
    
    messages = [{"role": "system", "content": system_msg}]
    
    while True:
        user_input = input("\nYou: ").strip()
        
        if user_input.lower() in ['quit', 'exit']:
            print("Goodbye!")
            break
        
        if not user_input:
            continue
        
        messages.append({"role": "user", "content": user_input})
        
        # Call LLM with tool available and streaming enabled
        print("\nAssistant: ", end='', flush=True)
        response = call_llm(messages, tools=[STORE_FACT_TOOL], stream=True)

        if not response:
            print("\nFailed to get response from LLM")
            continue

        message = response["choices"][0]["message"]
        tool_calls_raw = message.get("tool_calls")

        # If there are tool calls, handle them and continue the conversation
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
                args = json.loads(tool_call["function"]["arguments"])
                tool_call_id = tool_call.get("id", f"call_{i}")

                result = ""
                if func_name == "store_fact":
                    fact = args.get("fact")
                    if fact:
                        if save_fact(fact):
                            print(f"[📝 Stored: {fact}]")
                            result = f"Stored fact: {fact}"
                        else:
                            print(f"[Already know: {fact}]")
                            result = f"Already knew: {fact}"

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "name": func_name,
                    "content": result
                })

            # Call LLM again to continue conversation after tool use
            print("Assistant: ", end='', flush=True)
            response = call_llm(messages, tools=[STORE_FACT_TOOL], stream=True)
            if response:
                message = response["choices"][0]["message"]

        print()  # Newline after streaming completes

        # Add final assistant response to message history
        assistant_text = message.get("content", "")
        if assistant_text:
            messages.append({"role": "assistant", "content": assistant_text})

if __name__ == "__main__":
    main()
from __future__ import annotations

"""
Reading list app using OpenAI + Guttenread.

Flow:
- You provide a "reading list" as free-form text (file or stdin).
- The OpenAI model:
  - Cleans up and normalizes the titles.
  - Decides which titles to look up.
  - Calls the `search_gutenberg` tool as needed.
- The tool implementation reuses the local `search_gutenberg` function
  from `guttenread_mcp.server`, so the model gets back structured
  Project Gutenberg metadata (and optional text excerpts).

Requirements:
- Environment variable OPENAI_API_KEY must be set.
- Conda env / Python deps installed (see README.md).
"""

import argparse
import json
import os
from typing import Any, Dict, List

from openai import OpenAI

from guttenread_mcp.server import search_gutenberg


def read_input_text(path: str | None) -> str:
    if path:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    print("Paste your reading list (Ctrl-D to end on Unix / Ctrl-Z then Enter on Windows):")
    return "".join(iter(input, ""))  # type: ignore[arg-type]


def build_tools_spec() -> List[Dict[str, Any]]:
    """
    Define the tool schema that the OpenAI model sees.
    The actual implementation is in this script (we call search_gutenberg).
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "search_gutenberg",
                "description": (
                    "Search Project Gutenberg (via the Gutendex API) for books "
                    "matching the given titles, returning structured metadata "
                    "and optionally text excerpts."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "titles": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "A list of normalized book titles to search for. "
                                "You should deduplicate titles and remove obviously invalid entries."
                            ),
                        },
                        "max_results_per_title": {
                            "type": "integer",
                            "description": "Maximum number of matches per title.",
                            "default": 3,
                        },
                        "download_text": {
                            "type": "boolean",
                            "description": (
                                "If true, download text excerpts for the matches. "
                                "Use this only if you actually need to read/summarize the text."
                            ),
                            "default": False,
                        },
                        "max_chars": {
                            "type": ["integer", "null"],
                            "description": (
                                "If set, truncate downloaded texts to at most this many characters. "
                                "Use a smaller number (e.g. 5000) for summaries."
                            ),
                            "default": 20000,
                        },
                    },
                    "required": ["titles"],
                },
            },
        }
    ]


def call_search_gutenberg_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Local implementation of the `search_gutenberg` tool that the model calls.
    We just forward to the existing async function and return its result.
    """
    import asyncio

    titles = args.get("titles") or []
    max_results_per_title = int(args.get("max_results_per_title", 3))
    download_text = bool(args.get("download_text", False))
    max_chars = args.get("max_chars", 20000)

    if max_chars is not None:
        max_chars = int(max_chars)

    return asyncio.run(
        search_gutenberg(
            titles=titles,
            max_results_per_title=max_results_per_title,
            download_text=download_text,
            max_chars=max_chars,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Reading list app using OpenAI + Guttenread.")
    parser.add_argument(
        "--input-file",
        type=str,
        help="Path to a text file containing your reading list. If omitted, stdin will be used.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o-mini",
        help="OpenAI model name to use (default: gpt-4o-mini).",
    )
    parser.add_argument(
        "--download-text",
        action="store_true",
        help="Ask the model to download text excerpts for each matched book.",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=5000,
        help="Max characters per book text when download-text is used (default: 5000).",
    )
    args = parser.parse_args()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set.")

    client = OpenAI(api_key=api_key)

    reading_list_text = read_input_text(args.input_file)

    system_message = (
        "You are an assistant that helps organize reading lists and look up books "
        "on Project Gutenberg via a `search_gutenberg` tool.\n\n"
        "1. Carefully read the user's reading list text, which may contain messy "
        "bullet points, comments, and partial titles.\n"
        "2. Normalize it into a set of likely book titles (and authors if present).\n"
        "3. Decide which entries are actual books and which are comments or notes; ignore non-book entries.\n"
        "4. Call the `search_gutenberg` tool with a clean, deduplicated list of titles.\n"
        "5. When interpreting tool results, be STRICT:\n"
        "   - Only treat a book as 'found on Project Gutenberg' if the title is the same or very similar,\n"
        "     and the author and subject matter clearly match.\n"
        "   - If results only match on a generic word (e.g. 'labyrinths', 'patria', 'moment') or look unrelated,\n"
        "     say that the book is NOT available on Project Gutenberg instead of listing those loose matches.\n"
        "   - For obviously modern works (roughly 20th/21st century) that have no strong matches, explicitly say\n"
        "     they are likely not in the public domain and therefore not on Project Gutenberg.\n"
        "   - Do NOT invent matches or URLs.\n"
        "6. Present a nicely formatted summary of the reading list. For each original requested book, either:\n"
        "   - Show the best-matching Gutenberg entry (title, author(s), language(s), Gutenberg URL), or\n"
        "   - Clearly state that it does not appear to be available on Project Gutenberg.\n"
        "7. If text excerpts were downloaded, you may provide very brief summaries, but keep them concise."
    )

    user_instruction = (
        "Here is my reading list. Normalize the titles, then use the `search_gutenberg` tool "
        "to look them up on Project Gutenberg. Finally, give me a clean, structured summary.\n\n"
        f"READING LIST:\n{reading_list_text}"
    )

    tools = build_tools_spec()

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_instruction},
    ]

    # Let the model know whether it should fetch texts
    tool_call_defaults = {
        "download_text": args.download_text,
        "max_chars": args.max_chars,
    }

    while True:
        completion = client.chat.completions.create(
            model=args.model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )

        message = completion.choices[0].message

        if message.tool_calls:
            # The model wants to call one or more tools
            messages.append(
                {
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [tc.model_dump() for tc in message.tool_calls],
                }
            )

            for tool_call in message.tool_calls:
                name = tool_call.function.name
                raw_args = tool_call.function.arguments or "{}"
                try:
                    parsed_args = json.loads(raw_args)
                except json.JSONDecodeError:
                    parsed_args = {}

                if name == "search_gutenberg":
                    merged_args = {**tool_call_defaults, **parsed_args}
                    tool_result = call_search_gutenberg_tool(merged_args)
                else:
                    tool_result = {"error": f"Unknown tool {name}"}

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": name,
                        "content": json.dumps(tool_result),
                    }
                )

            # Loop again so the model can see tool results and produce a final answer
            continue

        # No tool calls: final answer
        messages.append({"role": "assistant", "content": message.content})
        print("\n=== MODEL OUTPUT ===\n")
        print(message.content or "")
        break


if __name__ == "__main__":
    main()



from __future__ import annotations

"""
Simple CLI for the Guttenread MCP logic, without using MCP.

This lets you:
- Type a list of book titles.
- Query Gutendex for matches.
- Optionally download text excerpts.
- See a concise summary in the terminal.
"""

import argparse
import asyncio
from typing import List

from guttenread_mcp.server import search_gutenberg


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search Project Gutenberg via Gutendex.")
    parser.add_argument(
        "titles",
        nargs="*",
        help="Book titles to search for. If omitted, you'll be prompted.",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=3,
        help="Maximum number of matches per title (default: 3).",
    )
    parser.add_argument(
        "--download-text",
        action="store_true",
        help="Download text excerpts as well (can be slower).",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=20000,
        help="Maximum characters per downloaded text (default: 20000).",
    )
    return parser.parse_args()


def prompt_for_titles() -> List[str]:
    raw = input("Enter book titles (comma- or semicolon-separated): ").strip()
    if not raw:
        return []
    # Split on comma or semicolon
    parts: List[str] = []
    for chunk in raw.replace(";", ",").split(","):
        title = chunk.strip()
        if title:
            parts.append(title)
    return parts


async def run_cli() -> None:
    args = parse_args()
    titles: List[str] = args.titles or prompt_for_titles()

    if not titles:
        print("No titles provided. Exiting.")
        return

    print(f"Searching Gutendex for {len(titles)} title(s)...\n")

    result = await search_gutenberg(
        titles=titles,
        max_results_per_title=args.max_results,
        download_text=args.download_text,
        max_chars=args.max_chars,
    )

    for entry in result.get("results", []):
        query = entry.get("query")
        error = entry.get("error")
        matches = entry.get("matches", [])

        print("=" * 80)
        print(f"Query: {query}")
        if error:
            print(f"  Error: {error}")
        if not matches:
            print("  No matches found. Try a shorter or partial title, or search by author name.")
            continue

        for idx, match in enumerate(matches, start=1):
            title = match.get("title")
            book_id = match.get("id")
            authors = match.get("authors") or []
            author_names = ", ".join(a.get("name") or "Unknown" for a in authors) or "Unknown"
            languages = ", ".join(match.get("languages") or []) or "Unknown"
            gutenberg_url = match.get("gutenberg_url")
            download_count = match.get("download_count")

            print(f"\n  Match {idx}:")
            print(f"    Title: {title}")
            print(f"    Author(s): {author_names}")
            print(f"    Gutenberg ID: {book_id}")
            print(f"    Languages: {languages}")
            if download_count is not None:
                print(f"    Download count: {download_count}")
            if gutenberg_url:
                print(f"    Gutenberg URL: {gutenberg_url}")

            if args.download_text:
                text = match.get("text")
                text_error = match.get("text_error")
                if text_error:
                    print(f"    Text error: {text_error}")
                elif text:
                    preview = text[:400].replace("\n", " ")
                    print(f"    Text preview ({len(text)} chars): {preview}...")
                else:
                    print("    No text available.")


def main() -> None:
    asyncio.run(run_cli())


if __name__ == "__main__":
    main()



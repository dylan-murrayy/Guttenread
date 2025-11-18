"""
Guttenread MCP server
---------------------

This MCP server exposes a single tool, `search_gutenberg`, which:
- Accepts a list of book titles.
- Queries the Gutendex API (Project Gutenberg) for each title.
- Returns structured metadata and optional text excerpts or full texts.

It is designed to be used by an MCP-capable AI client, where the human
can type e.g. "Find these books: Pride and Prejudice; Dracula" and the
model can call this tool to retrieve the data.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Tuple

import requests
from mcp.server.fastmcp import FastMCP


# Name the server so it shows up clearly in your MCP client.
mcp = FastMCP("guttenread-gutendex")


GUTENDEX_BASE_URL = "https://gutendex.com/books"


def _pick_best_text_format(formats: Dict[str, str]) -> Optional[str]:
    """
    Choose the most suitable text URL from a Gutendex `formats` dict.

    Preference order:
    - text/plain; charset=utf-8
    - text/plain; charset=us-ascii
    - text/plain
    - text/html; charset=utf-8
    - text/html
    """
    if not formats:
        return None

    preferred_keys = [
        "text/plain; charset=utf-8",
        "text/plain; charset=us-ascii",
        "text/plain",
        "text/html; charset=utf-8",
        "text/html",
    ]

    for key in preferred_keys:
        url = formats.get(key)
        if url and isinstance(url, str):
            # Exclude zipped / binary variants if they slip in
            if not url.lower().endswith(".zip"):
                return url

    # Fallback: any text/* that is not a zip
    for key, url in formats.items():
        if not isinstance(url, str):
            continue
        if key.startswith("text/") and not url.lower().endswith(".zip"):
            return url

    return None


def _search_gutendex(title: str, max_results: int) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Search Gutendex for a single title.

    Returns (results, error_message). If error_message is not None, an error occurred.
    """
    try:
        response = requests.get(
            GUTENDEX_BASE_URL,
            params={"search": title},
            timeout=15,
        )
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        return [], f"HTTP error while querying Gutendex: {exc}"

    try:
        data = response.json()
    except Exception as exc:  # noqa: BLE001
        return [], f"Failed to decode JSON response from Gutendex: {exc}"

    results = data.get("results", [])
    if not isinstance(results, list):
        return [], "Unexpected Gutendex response format: 'results' is not a list"

    return results[:max_results], None


def _download_text(url: str, max_chars: Optional[int]) -> Tuple[Optional[str], Optional[str]]:
    """
    Download text content from the given URL.

    Returns (text_or_excerpt, error_message).
    """
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        return None, f"HTTP error while downloading text: {exc}"

    # Try best-effort decoding; Gutendex typically returns UTF-8.
    resp.encoding = resp.encoding or "utf-8"
    text = resp.text

    if max_chars is not None and max_chars > 0 and len(text) > max_chars:
        return text[:max_chars], None

    return text, None


def _normalize_book(book: Dict[str, Any], download_text: bool, max_chars: Optional[int]) -> Dict[str, Any]:
    """
    Turn a raw Gutendex `book` record into a compact, structured dict.
    Optionally download the text (or an excerpt) if available.
    """
    book_id = book.get("id")
    title = book.get("title")
    languages = book.get("languages") or []
    download_count = book.get("download_count")
    subjects = book.get("subjects") or []
    bookshelves = book.get("bookshelves") or []
    copyright_ = book.get("copyright")
    formats = book.get("formats") or {}

    # Authors come as a list of objects with 'name', 'birth_year', 'death_year'
    raw_authors = book.get("authors") or []
    authors: List[Dict[str, Any]] = []
    for author in raw_authors:
        if not isinstance(author, dict):
            continue
        authors.append(
            {
                "name": author.get("name"),
                "birth_year": author.get("birth_year"),
                "death_year": author.get("death_year"),
            }
        )

    # Build canonical Gutenberg URL if we have an ID
    gutenberg_url = None
    if isinstance(book_id, int):
        gutenberg_url = f"https://www.gutenberg.org/ebooks/{book_id}"

    text_url = _pick_best_text_format(formats)

    text: Optional[str] = None
    text_error: Optional[str] = None
    if download_text and text_url:
        text, text_error = _download_text(text_url, max_chars=max_chars)

    normalized: Dict[str, Any] = {
        "id": book_id,
        "title": title,
        "authors": authors,
        "languages": languages,
        "download_count": download_count,
        "subjects": subjects,
        "bookshelves": bookshelves,
        "copyright": copyright_,
        "gutenberg_url": gutenberg_url,
        "text_url": text_url,
    }

    if download_text:
        normalized["text"] = text
        if text_error:
            normalized["text_error"] = text_error

    return normalized


@mcp.tool()
async def search_gutenberg(
    titles: List[str],
    max_results_per_title: int = 3,
    download_text: bool = False,
    max_chars: Optional[int] = 20000,
) -> Dict[str, Any]:
    """
    Search Project Gutenberg via Gutendex for a list of titles.

    Parameters
    ----------
    titles:
        A list of book titles or partial titles to search for.
    max_results_per_title:
        Maximum number of matches to return per input title.
    download_text:
        If True, attempt to download the text for each matched book.
        Be aware that this can be slow and result in large responses.
    max_chars:
        If set (default 20,000), truncate downloaded texts to at most
        this many characters. Set to None to return full texts.

    Returns
    -------
    dict with the shape:
    {
      "results": [
        {
          "query": "<original title string>",
          "matches": [
            {
              "id": ...,
              "title": ...,
              "authors": [{"name": ..., "birth_year": ..., "death_year": ...}],
              "languages": [...],
              "download_count": ...,
              "subjects": [...],
              "bookshelves": [...],
              "copyright": ...,
              "gutenberg_url": "https://www.gutenberg.org/ebooks/<id>",
              "text_url": "...",
              "text": "... (optional, if download_text=True)",
              "text_error": "... (optional, if a download error occurred)",
            },
            ...
          ],
          "error": "... (optional, if the Gutendex query failed)",
        },
        ...
      ]
    }
    """
    if not isinstance(titles, list):
        raise TypeError("titles must be a list of strings")

    cleaned_titles = [t for t in (str(t).strip() for t in titles) if t]
    if not cleaned_titles:
        return {"results": []}

    if max_results_per_title <= 0:
        max_results_per_title = 1

    results: List[Dict[str, Any]] = []

    loop = asyncio.get_event_loop()

    # Because `requests` is synchronous, offload HTTP calls to a thread pool
    async def handle_single_title(q: str) -> Dict[str, Any]:
        raw_results, error = await loop.run_in_executor(None, _search_gutendex, q, max_results_per_title)

        match_dicts: List[Dict[str, Any]] = []
        if raw_results:
            for book in raw_results:
                if not isinstance(book, dict):
                    continue
                match_dicts.append(_normalize_book(book, download_text=download_text, max_chars=max_chars))

        entry: Dict[str, Any] = {
            "query": q,
            "matches": match_dicts,
        }
        if error:
            entry["error"] = error

        return entry

    tasks = [handle_single_title(q) for q in cleaned_titles]
    for entry in await asyncio.gather(*tasks):
        results.append(entry)

    return {"results": results}


def main() -> None:
    """Entry point for running the MCP server via stdio."""
    mcp.run()


if __name__ == "__main__":
    main()



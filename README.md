## Guttenread Reading List App

This project is a small **reading list app** that uses OpenAI plus Project
Gutenberg (via the **Gutendex** API) to clean up a messy reading list and tell
you which books are available on Project Gutenberg.

Under the hood it reuses a single function:

- **`search_gutenberg`**: Given a list of book titles, returns structured
  search results and (optionally) text excerpts or full texts from Gutendex.

The reading list app wires this up as a **local tool** for the OpenAI Chat
Completions API. You do **not** need to configure MCP or an IDE integration to
use it.

### 1. Setup (with Conda)

From the project root:

```bash
cd /Users/dylan/Documents/Cursor/Guttenread
conda env create -f environment.yml
conda activate guttenread
```

If you prefer to create the environment manually without `environment.yml`:

```bash
cd /Users/dylan/Documents/Cursor/Guttenread
conda create -n guttenread python=3.11 -y
conda activate guttenread
pip install -r requirements.txt
```

### 2. OpenAI reading list app (main demo)

The main entry point is `reading_list_app.py`, which:
- Takes a messy reading list (file or pasted text),
- Uses an OpenAI model to normalize and clean up the titles,
- Then calls the same `search_gutenberg` logic as a tool to look them up,
- Finally prints a structured summary of your reading list.

> Make sure `OPENAI_API_KEY` is set in your environment before running:
>
> ```bash
> export OPENAI_API_KEY=sk-...
> ```

From the project root (with the `guttenread` Conda env activated):

```bash
cd /Users/dylan/Documents/Cursor/Guttenread
python reading_list_app.py --input-file my_reading_list.txt
```

If you omit `--input-file`, it will read from stdin:

```bash
python reading_list_app.py
```

By default it uses `gpt-4o-mini`. You can change the model, or tell it to fetch text excerpts:

```bash
python reading_list_app.py --model gpt-4o --download-text --max-chars 5000
```

The app will:
- Parse your reading list text,
- Let the model decide which entries are actual books,
- Call the `search_gutenberg` tool with a normalized title list,
- Then print a human-friendly summary with titles, authors, languages, and Gutenberg URLs.

### 3. Tool: `search_gutenberg` (shared logic)

**Signature (conceptual):**

- **`search_gutenberg(titles, max_results_per_title=3, download_text=False, max_chars=20000)`**

**Parameters:**

- **`titles`** (`List[str]`): List of book titles or partial titles.
- **`max_results_per_title`** (`int`): Max matches per title (default: 3).
- **`download_text`** (`bool`): If `true`, the server will fetch the text for
  each matched book (can be large / slower).
- **`max_chars`** (`int | null`): If set, truncate downloaded texts to at most
  this many characters (default: 20,000). Use `null` for full text.

**Return shape (JSON):**

```json
{
  "results": [
    {
      "query": "Pride and Prejudice",
      "matches": [
        {
          "id": 1342,
          "title": "Pride and Prejudice",
          "authors": [
            {
              "name": "Austen, Jane",
              "birth_year": 1775,
              "death_year": 1817
            }
          ],
          "languages": ["en"],
          "download_count": 54728,
          "subjects": ["Courtship -- Fiction", "..."],
          "bookshelves": ["Best Books Ever Listings", "..."],
          "copyright": false,
          "gutenberg_url": "https://www.gutenberg.org/ebooks/1342",
          "text_url": "https://www.gutenberg.org/cache/epub/1342/pg1342.txt",
          "text": "First N characters of the book text (if download_text=true)",
          "text_error": "Optional error message if text download failed"
        }
      ],
      "error": "Optional error message if the Gutendex search failed"
    }
  ]
}
```

If Gutendex returns **no matches** for a given query:

- The `matches` array will simply be empty for that `query`.
- In the CLI, you will see:  
  `No matches found. Try a shorter or partial title, or search by author name.`

### 4. Optional: MCP server

If you want, the same `search_gutenberg` logic is also exposed as an MCP server
in `guttenread_mcp/server.py`. This is **optional** and not required for the
reading list app.

The MCP server is designed to run over **stdio**, as expected by MCP clients.
In an MCP-capable IDE or chat environment you can configure a server entry
named `guttenread-gutendex` that runs:

- **Command**: `python`
- **Args**: `-m`, `guttenread_mcp.server`

Once configured, the client will discover the same `search_gutenberg` tool and
can call it directly. The behavior and JSON shape are identical to what the
reading list app uses.



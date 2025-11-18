## Guttenread MCP Server (Python)

This directory contains a small **Python MCP server** that lets an AI agent
search Project Gutenberg (via the **Gutendex** API), fetch metadata, and
optionally download book texts.

The main tool it exposes is:

- **`search_gutenberg`**: Given a list of book titles, returns structured
  search results and (optionally) text excerpts or full texts.

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

### 2. Using the CLI (no MCP / IDE wiring required)

You can call the same logic directly from the terminal via `cli.py`.

From the project root (with the `guttenread` Conda env activated):

```bash
cd /Users/dylan/Documents/Cursor/Guttenread
python cli.py
```

This will prompt you for titles, e.g.:

```text
Pride and Prejudice; Dracula; Frankenstein
```

You can also pass titles on the command line:

```bash
python cli.py "Pride and Prejudice" Dracula Frankenstein
```

And you can request text excerpts as well:

```bash
python cli.py "Pride and Prejudice" --max-results 1 --download-text --max-chars 5000
```

The CLI prints, for each query:
- The title, authors, Gutenberg ID, language(s), download count, and Gutenberg URL.
- If `--download-text` is used, a short preview and total character count for the text.

### 3. OpenAI reading list app

You can also run a small **OpenAI-powered app** that:
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

### 4. Running the MCP server

The server is implemented in `guttenread_mcp/server.py` and is designed to run
over **stdio**, as expected by MCP clients.

To run it directly (for testing):

```bash
cd /Users/dylan/Documents/Cursor/Guttenread
python -m guttenread_mcp.server
```

In practice, an MCP-capable AI client (such as a compatible IDE or chat
environment) will launch this server **as a subprocess over stdio** using a
configuration entry similar to:

```json
{
  "name": "guttenread-gutendex",
  "command": "python",
  "args": [
    "-m",
    "guttenread_mcp.server"
  ]
}
```

> Check your specific MCP client’s documentation for the exact config format.

### 5. Tool: `search_gutenberg`

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

### 6. How you might use this in an app

Once your MCP client is configured to use this server, you can build a simple
app (or just chat with the model) using prompts like:

- **“Given the titles ‘Pride and Prejudice’, ‘Dracula’, and ‘Frankenstein’,
  call the `search_gutenberg` tool and show me a table of the matches with
  authors, languages, and Gutenberg URLs.”**
- **“Use `search_gutenberg` to fetch the text for the top match of ‘Dracula`
  and summarize it in 10 bullet points.”**

The AI agent will handle calling the MCP tool and returning structured results
to your app or UI.



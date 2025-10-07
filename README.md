# MCP Playwright Scanner (PoC)

A small Python console application that launches a Chromium browser using Playwright, lets you navigate to a page, and upon command scans for interactable elements, generating robust XPath locators for each.

Note: This proof-of-concept uses Playwright directly from Python. It is structured so it can be adapted to an MCP server/client flow if needed.

## Requirements
- Python 3.9+
- Playwright Python package and browser binaries

## Installation

1. Install dependencies:

```bash
pip install -e .
```

2. Install Playwright browser binaries (one-time):

```bash
python -m playwright install
```

## Usage

Run the console app:

```bash
mcp-scan
```

You will see a Chromium window open and a prompt in your terminal. Available commands:

- `url <https://...>` Navigate the opened page to a specific URL.
- `scan` Scan current page for interactable elements and print best-effort unique XPath locators along with JSON output.
- `help` Show commands.
- `quit` or `exit` Close the browser and exit.

Example session:

```
$ mcp-scan
MCP Playwright Scanner
Commands:
  url <https://...>  -> navigate to a URL in the opened page
  scan               -> scan current page for interactable elements and print XPaths
  help               -> show this help
  quit/exit          -> close browser and exit
Launching Chromium...
Browser launched. You can now type 'url <address>' to navigate, or manually navigate in the opened window.
mcp> url https://example.com
mcp> scan
Found 4 interactable elements:
#1: <a> text='More information'
    xpath: //a[normalize-space(.)='More information']
...
```

## How XPath generation works (summary)

- Prefer unique `id` when available.
- Try strong attributes (`data-testid`, `data-test`, `data-qa`, `name`, `aria-label`, `title`).
- Use text for links/buttons.
- For inputs, attempt label association.
- Combine tag + multiple attribute predicates, optionally narrowing with contains(text).
- Consider nearest ancestor with a stable attribute.
- Fallback to indexed selector when necessary.

Each candidate XPath is validated for uniqueness on the current DOM; if not unique, the builder tries stronger/narrower options before falling back to an index.

## Notes
- Increase default timeouts or adjust logic as needed for heavy/SPA pages.
- The scanner looks for typical interactable elements: links, buttons, inputs (non-hidden), selects, textareas, role=button, tabindex, and contenteditable=true.

# MCP Playwright Scanner (PoC)

A small Python console application that launches a Chromium browser using Playwright, lets you navigate to a page, and upon command scans for interactable elements, generating robust locators for each element: XPath, CSS, id (when available), and Playwright role-based locators.

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
- `scan [output.json]` Scan current page for interactable elements and print best-effort unique locators (XPath, CSS, id, Playwright role). If `output.json` is provided, the JSON results will be saved to that file as well.
- `help` Show commands.
- `quit` or `exit` Close the browser and exit.

Example session:

```
$ mcp-scan
MCP Playwright Scanner
Commands:
  url <https://...>  -> navigate to a URL in the opened page
  scan               -> scan current page for interactable elements and print locators (XPath, CSS, id, role)
  help               -> show this help
  quit/exit          -> close browser and exit
Launching Chromium...
Browser launched. You can now type 'url <address>' to navigate, or manually navigate in the opened window.
mcp> url https://example.com
mcp> scan
Found 4 interactable elements:
#1: <a> text='More information'
    id: None
    xpath: //a[normalize-space(.)='More information']
    css: a[href]
    role: get_by_role('link', name='More information')
...
```

## How locator generation works (summary)

- id: If the element has an id and it is unique, it is reported and used directly.
- XPath: Prefer unique id; then strong attributes (`data-testid`, `data-test`, `data-qa`, `name`, `aria-label`, `title`); for links/buttons try text; for inputs try associated label; combine tag+attributes; try stable ancestor; fallback to an index.
- CSS: Prefer #id or [id="..."]; try strong attributes; combine tag+attributes; narrow via stable ancestor; fallback to :nth-of-type under ancestor/body.
- Playwright role: Infer ARIA role (explicit role attribute or implicit from tag/type/href) and an accessible name (aria-label/title/alt/label or text). If `get_by_role(role, name=...)` is unique, it's reported.

Each candidate is validated for uniqueness against the live DOM before being accepted; otherwise, the builder proceeds to stronger/narrower options or safe fallbacks.

## Notes
- Increase default timeouts or adjust logic as needed for heavy/SPA pages.
- The scanner looks for typical interactable elements: links, buttons, inputs (non-hidden), selects, textareas, role=button, tabindex, and contenteditable=true.

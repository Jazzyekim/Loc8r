from __future__ import annotations

import json

from playwright.sync_api import sync_playwright, Page

from .xpath_builder import scan_interactables

BANNER = (
    "MCP Playwright Scanner\n"
    "Commands:\n"
    "  url <https://...>  -> navigate to a URL in the opened page\n"
    "  scan               -> scan current page for interactable elements and print XPaths\n"
    "  help               -> show this help\n"
    "  quit/exit          -> close browser and exit\n"
)


def _print_scan(page: Page) -> None:
    items = scan_interactables(page)
    print(f"Found {len(items)} interactable elements:\n")
    for i, it in enumerate(items, 1):
        if "error" in it:
            print(f"#{i}: ERROR: {it['error']}")
            continue
        tag = it.get("tag")
        txt = (it.get("text") or "")
        txt_disp = txt if len(txt) <= 120 else txt[:117] + "..."
        xp = it.get("xpath")
        print(f"#{i}: <{tag}> text='{txt_disp}'\n    xpath: {xp}")
    print()
    print("JSON output (copy-paste if needed):")
    print(json.dumps(items, ensure_ascii=False, indent=2))


def main() -> None:
    print(BANNER)
    print("Launching Chromium...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(5000)
        page.goto("about:blank")
        print("Browser launched. You can now type 'url <address>' to navigate, or manually navigate in the opened window.")

        while True:
            try:
                raw = input("mcp> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting...")
                break
            if not raw:
                continue
            cmd, *rest = raw.split(maxsplit=1)
            cmd = cmd.lower()
            arg = rest[0] if rest else ""

            if cmd in ("quit", "exit"):
                break
            elif cmd == "help":
                print(BANNER)
            elif cmd == "url":
                if not arg:
                    print("Usage: url https://example.com")
                    continue
                try:
                    page.goto(arg)
                    print(f"Navigated to {page.url}")
                except Exception as e:
                    print(f"Navigation failed: {e}")
            elif cmd == "scan":
                try:
                    _print_scan(page)
                except Exception as e:
                    print(f"Scan failed: {e}")
            else:
                print("Unknown command. Type 'help' for commands.")

        try:
            context.close()
            browser.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()

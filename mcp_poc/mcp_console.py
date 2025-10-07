from __future__ import annotations

import json
from typing import Optional

from playwright.sync_api import sync_playwright, Page

from .xpath_builder import scan_interactables

BANNER = (
    "MCP Playwright Scanner\n"
    "Commands:\n"
    "  url <https://...>      -> navigate to a URL in the opened page\n"
    "  scan [output.json]     -> scan page for interactable elements and print locators; optionally save JSON to file\n"
    "  help                   -> show this help\n"
    "  quit/exit              -> close browser and exit\n"
)


def _print_scan(page: Page, out_path: Optional[str] = None) -> None:
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
        css = it.get("css")
        idv = it.get("id")
        role = it.get("role")
        role_str = None
        if isinstance(role, dict) and role.get("role"):
            if role.get("name"):
                role_str = f"get_by_role('{role['role']}', name='{role['name']}')"
            else:
                role_str = f"get_by_role('{role['role']}')"
        print(
            f"#{i}: <{tag}> text='{txt_disp}'\n"
            f"    id: {idv}\n"
            f"    xpath: {xp}\n"
            f"    css: {css}\n"
            f"    role: {role_str}"
        )
    print()
    print("JSON output (copy-paste if needed):")
    json_text = json.dumps(items, ensure_ascii=False, indent=2)
    print(json_text)
    if out_path:
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(json_text)
            print(f"Saved scan results to: {out_path}")
        except Exception as e:
            print(f"Failed to save results to '{out_path}': {e}")


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
                    out_path = arg if arg else None
                    _print_scan(page, out_path)
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

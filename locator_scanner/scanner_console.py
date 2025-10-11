from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright, Page

from .codegen_pf import (
    generate_for_file,
    DEFAULT_PACKAGE,
    DEFAULT_TIMEOUT,
    DEFAULT_NAME_ANNOTATION_IMPORT,
)
from .xpath_builder import scan_interactables

BANNER = (
    "Loc8r Playwright Scanner\n"
    "Commands:\n"
    "  url <https://...>      -> navigate to a URL in the opened page\n"
    "  scan [output.json]     -> scan page for interactable elements and print locators; optionally save JSON to file\n"
    "  codegen <json> [PageName] [outDir] -> generate Java Page Object (@FindBy) from scan JSON; prompts for PageName if omitted\n"
    "  help [command]         -> show general help or detailed help for a command (e.g., 'help codegen')\n"
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
        name = it.get("name") or ""
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
            f"    name: {name}\n"
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
                raw = input("loc8r> ").strip()
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
                # Detailed help: allow 'help codegen', 'help scan', etc.
                topic = arg.strip().lower()
                if not topic:
                    print(BANNER)
                    print("Type 'help codegen' for detailed generator usage, or 'help scan' / 'help url'.")
                else:
                    if topic == "codegen":
                        print(
                            "\nCode generation (PageFactory, @FindBy)\n"
                            "Usage: codegen <json> [PageName] [outDir]\n"
                            "  <json>     Path to a scan JSON file produced by 'scan'\n"
                            "  [PageName] Base page name (e.g., Login). The class will be '<Name>Page'. If omitted, you'll be prompted.\n"
                            "  [outDir]   Output root (default: src/test/java). Package path is created within it.\n\n"
                            "Examples:\n"
                            "  codegen masha.json Login src/test/java\n"
                            "  codegen login.json   # will prompt for page name\n\n"
                            "Notes:\n"
                            "- Uses stable-first locator priority: data-test/testid → id → name → css → xpath.\n"
                            "- Fields and class are annotated with @Name; configure import via the standalone CLI 'loc8r-codegen'.\n"
                            "- For more advanced options (package, timeout, annotation import), use the standalone CLI:\n"
                            "    loc8r-codegen --input masha.json --package com.example.pages --class-name Login --out src/test/java\n"
                        )
                    elif topic == "scan":
                        print(
                            "\nScan current page for interactable elements\n"
                            "Usage: scan [output.json]\n"
                            "  Without argument: prints found elements and their locators (XPath, CSS, id, role).\n"
                            "  With output.json: also saves the JSON results to the given file.\n"
                        )
                    elif topic == "url":
                        print(
                            "\nNavigate to URL in the opened browser\n"
                            "Usage: url <https://...>\n"
                            "  Example: url https://example.com\n"
                        )
                    elif topic in ("quit", "exit"):
                        print(
                            "\nExit Loc8r\n"
                            "Usage: quit | exit\n"
                            "  Closes the browser and terminates the session.\n"
                        )
                    else:
                        print(f"Unknown help topic: {topic}. Type 'help' to see available commands.")
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
            elif cmd == "codegen":
                # Usage: codegen <json> [PageName] [outDir]
                try:
                    if not arg:
                        print("Usage: codegen <json> [PageName] [outDir]\nFor detailed options and examples, type: help codegen")
                    else:
                        parts = arg.split()
                        json_path_str = parts[0]
                        page_name = None
                        out_dir_str = "src/test/java"
                        if len(parts) >= 2:
                            page_name = parts[1]
                        if len(parts) >= 3:
                            out_dir_str = parts[2]
                        if not page_name:
                            try:
                                page_name = input("Provide the page name (e.g., Login): ").strip()
                            except (EOFError, KeyboardInterrupt):
                                page_name = ""
                        if not page_name:
                            print("Page name is required. Aborting codegen.")
                        else:
                            out_path = generate_for_file(
                                json_path=Path(json_path_str),
                                package=DEFAULT_PACKAGE,
                                provided_page_name=page_name,
                                out_dir=Path(out_dir_str),
                                timeout_seconds=DEFAULT_TIMEOUT,
                                name_annotation_import=DEFAULT_NAME_ANNOTATION_IMPORT,
                            )
                            print(f"Generated: {out_path}")
                except Exception as e:
                    print(f"Code generation failed: {e}")
            else:
                print("Unknown command. Type 'help' for commands.")

        try:
            context.close()
            browser.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()

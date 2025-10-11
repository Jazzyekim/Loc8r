from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .locators_pf import pick_findby
from .naming_pf import to_field_base, dedupe_names, to_class_name

DEFAULT_PACKAGE = "com.example.pages"
DEFAULT_TIMEOUT = 5
DEFAULT_NAME_ANNOTATION_IMPORT = "com.example.annotations.Name"


@dataclass
class FieldDef:
    name: str
    display_name: str
    findby_attr: str
    findby_value: str


def _load_json(path: Path) -> List[Dict]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
        if not isinstance(data, list):
            raise ValueError(f"Expected a JSON array in {path}")
        return data


def _compute_fields(elements: List[Dict]) -> List[FieldDef]:
    bases = [to_field_base(e) for e in elements]
    unique_names = dedupe_names(bases)

    fields: List[FieldDef] = []
    for e, fname in zip(elements, unique_names):
        picked = pick_findby(e)
        if not picked:
            # Skip elements without suitable locator
            print(f"[codegen_pf] Warning: skipped element without stable locator: {e.get('tag')} name={e.get('name')} id={e.get('id')}", file=sys.stderr)
            continue
        attr, value = picked
        display_name = str(e.get("name") or e.get("id") or e.get("attributes", {}).get("name") or fname)
        fields.append(FieldDef(
            name=fname,
            display_name=display_name,
            findby_attr=attr,
            findby_value=value,
        ))

    # Deterministic sorting
    fields.sort(key=lambda f: f.name)
    return fields


def _render_class(package: str, class_name: str, provided_name: str, fields: List[FieldDef], timeout_seconds: int, name_annotation_import: str, template_dir: Path, out_dir: Path, source_file: Optional[Path] = None) -> Path:
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(enabled_extensions=(".j2",)),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    tmpl = env.get_template("templates_PageObjectPF.j2")
    java = tmpl.render(
        package_name=package,
        provided_name=provided_name,
        class_name=class_name,
        fields=[f.__dict__ for f in fields],
        timeout_seconds=timeout_seconds,
        name_annotation_import=name_annotation_import,
        source_path=str(source_file) if source_file else None,
    )

    # Create package directory structure
    package_path = Path(*package.split('.'))
    target_dir = out_dir / package_path
    target_dir.mkdir(parents=True, exist_ok=True)
    out_path = target_dir / f"{class_name}.java"
    out_path.write_text(java, encoding="utf-8")
    return out_path


def generate_for_file(json_path: Path, package: str, provided_page_name: str, out_dir: Path, timeout_seconds: int, name_annotation_import: str) -> Path:
    elements = _load_json(json_path)
    fields = _compute_fields(elements)
    class_name = to_class_name(provided_page_name)
    return _render_class(
        package=package,
        class_name=class_name,
        provided_name=provided_page_name,
        fields=fields,
        timeout_seconds=timeout_seconds,
        name_annotation_import=name_annotation_import,
        template_dir=Path(__file__).parent,
        out_dir=out_dir,
        source_file=json_path,
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Java PageFactory Page Objects from scanned locator JSON.")
    parser.add_argument("--input", "-i", required=True, help="Path to scan JSON file or directory containing JSON files.")
    parser.add_argument("--package", "-p", default=DEFAULT_PACKAGE, help=f"Java package for generated classes (default: {DEFAULT_PACKAGE}).")
    parser.add_argument("--class-name", "-c", help="Base page name (e.g., 'Login'); class will be '<Name>Page'. If omitted and input is a directory or multiple files, file stem will be used per file. If a single file, prompts interactively.")
    parser.add_argument("--out", "-o", default="src/test/java", help="Output root directory for generated .java files (default: src/test/java).")
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT, help=f"Timeout seconds for waits (default: {DEFAULT_TIMEOUT}).")
    parser.add_argument("--name-annotation-import", default=DEFAULT_NAME_ANNOTATION_IMPORT, help=f"Fully-qualified @Name annotation import (default: {DEFAULT_NAME_ANNOTATION_IMPORT}).")

    args = parser.parse_args(argv)

    in_path = Path(args.input)
    out_dir = Path(args.out)

    if in_path.is_file():
        provided = args.class_name
        if not provided:
            # Interactive prompt per requirements
            try:
                provided = input("Provide the page name (e.g., Login): ").strip()
            except (EOFError, KeyboardInterrupt):
                print("No page name provided.", file=sys.stderr)
                return 2
        if not provided:
            print("--class-name is required for single input file (or provide interactively).", file=sys.stderr)
            return 2
        out_path = generate_for_file(
            json_path=in_path,
            package=args.package,
            provided_page_name=provided,
            out_dir=out_dir,
            timeout_seconds=args.timeout_seconds,
            name_annotation_import=args.name_annotation_import,
        )
        print(f"Generated: {out_path}")
        return 0

    if in_path.is_dir():
        json_files = sorted([p for p in in_path.glob("*.json")])
        if not json_files:
            print(f"No JSON files found in directory: {in_path}", file=sys.stderr)
            return 2
        for jf in json_files:
            provided = args.class_name or jf.stem
            out_path = generate_for_file(
                json_path=jf,
                package=args.package,
                provided_page_name=provided,
                out_dir=out_dir,
                timeout_seconds=args.timeout_seconds,
                name_annotation_import=args.name_annotation_import,
            )
            print(f"Generated: {out_path}")
        return 0

    print(f"Input path not found: {in_path}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

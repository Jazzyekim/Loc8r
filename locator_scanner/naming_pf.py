from __future__ import annotations

import re
from typing import Dict, List

_CAMEL_INVALID = re.compile(r"[^A-Za-z0-9]+")


def to_field_base(element: Dict) -> str:
    attrs = element.get("attributes") or {}
    source = (
        element.get("id")
        or attrs.get("id")
        or attrs.get("name")
        or attrs.get("data-test")
        or element.get("tag")
        or "element"
    )
    parts = [p for p in _CAMEL_INVALID.sub(" ", str(source)).strip().split() if p]
    if not parts:
        return "element"
    head, *tail = parts
    return head.lower() + "".join(w.capitalize() for w in tail)


def dedupe_names(bases: List[str]) -> List[str]:
    seen = {}
    result = []
    for b in bases:
        if b not in seen:
            seen[b] = 1
            result.append(b)
        else:
            idx = seen[b]
            seen[b] = idx + 1
            result.append(f"{b}{idx}")
    return result


def to_class_name(provided: str) -> str:
    # Ensure PascalCase and append 'Page' suffix if not present
    parts = [p.capitalize() for p in _CAMEL_INVALID.sub(" ", str(provided)).strip().split() if p]
    name = "".join(parts) or "Page"
    if not name.endswith("Page"):
        name += "Page"
    return name

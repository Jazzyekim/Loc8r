from __future__ import annotations

from typing import Dict, Tuple, Optional


def escape_java_string(value: str) -> str:
    """Escape a string literal for inclusion inside double-quoted Java code."""
    return (
        value.replace("\\", "\\\\")
        .replace("\"", "\\\"")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def pick_findby(element: Dict) -> Optional[Tuple[str, str]]:
    """
    Decide which @FindBy to use for the element according to priority:
      1) data-test / data-testid -> css
      2) id -> id
      3) name -> name
      4) css -> css
      5) xpath -> xpath

    Returns (findby_attr, findby_value) or None if cannot decide.
    """
    attrs = (element.get("attributes") or {})
    data_test = attrs.get("data-test")
    data_testid = attrs.get("data-testid")
    if data_test:
        return "css", f"[data-test='" + escape_java_string(str(data_test)) + "']"
    if data_testid:
        return "css", f"[data-testid='" + escape_java_string(str(data_testid)) + "']"

    el_id = attrs.get("id") or element.get("id")
    if el_id:
        return "id", escape_java_string(str(el_id))

    el_name = attrs.get("name")
    if el_name:
        return "name", escape_java_string(str(el_name))

    css = element.get("css")
    if css:
        return "css", escape_java_string(str(css))

    xpath = element.get("xpath")
    if xpath:
        return "xpath", escape_java_string(str(xpath))

    return None

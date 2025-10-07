from __future__ import annotations

import re
from typing import List, Dict, Any, Optional, Tuple

from playwright.sync_api import Page, ElementHandle


def _escape_xpath_literal(s: str) -> str:
    # Handles quotes inside string for XPath literal
    if "'" not in s:
        return f"'{s}'"
    if '"' not in s:
        return f'"{s}"'
    parts = s.split("'")
    return "concat(" + ",".join([f"'{p}'" for p in parts[:-1]] + ["\"'\""] + [f"'{parts[-1]}'"]) + ")"


CANDIDATE_ATTRS = [
    "data-testid",
    "data-test",
    "data-qa",
    "aria-label",
    "name",
    "id",
    "title",
    "type",
    "role",
]

INTERACTABLE_CSS = [
    "a[href]",
    "button",
    "input:not([type='hidden'])",
    "textarea",
    "select",
    "[role='button']",
    "[tabindex]",
    "[contenteditable='true']",
]


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _try_unique(page: Page, xpath: str) -> Tuple[bool, int]:
    try:
        matches = page.locator(f"xpath={xpath}")
        count = matches.count()
        return count == 1, count
    except Exception:
        return False, 0


def _build_attribute_predicates(attrs: Dict[str, Optional[str]]) -> List[str]:
    preds = []
    for k, v in attrs.items():
        if not v:
            continue
        # skip overly long values
        if len(v) > 120:
            continue
        preds.append(f"@{k}={_escape_xpath_literal(v)}")
    return preds


def _get_element_basic_info(el: ElementHandle) -> Dict[str, Any]:
    return el.evaluate(
        "(node) => {\n"
        "  const txt = (node.innerText || node.textContent || '').trim();\n"
        "  const attrs = {};\n"
        "  for (const a of node.attributes || []) { attrs[a.name] = a.value; }\n"
        "  const tag = node.tagName ? node.tagName.toLowerCase() : 'unknown';\n"
        "  return { tag, text: txt, attrs };\n"
        "}"
    )


def build_xpath_for_element(page: Page, el: ElementHandle) -> str:
    info = _get_element_basic_info(el)
    tag = info.get("tag") or "*"
    text = _normalize_text(info.get("text") or "")
    attrs: Dict[str, str] = info.get("attrs") or {}

    # 1) id uniqueness
    el_id = attrs.get("id")
    if el_id:
        xpath = f"//*[@id={_escape_xpath_literal(el_id)}]"
        unique, _ = _try_unique(page, xpath)
        if unique:
            return xpath

    # 2) Strong attributes
    for strong in ["data-testid", "data-test", "data-qa", "name", "aria-label", "title"]:
        val = attrs.get(strong)
        if val:
            xpath = f"//{tag}[@{strong}={_escape_xpath_literal(val)}]"
            unique, _ = _try_unique(page, xpath)
            if unique:
                return xpath

    # 3) Buttons/links by text
    if tag in ("a", "button") and text:
        # Try exact normalized text
        xpath = f"//{tag}[normalize-space(.)={_escape_xpath_literal(text)}]"
        unique, _ = _try_unique(page, xpath)
        if unique:
            return xpath
        # Try contains
        short = text[:60]
        if short:
            xpath = f"//{tag}[contains(normalize-space(.), {_escape_xpath_literal(short)})]"
            unique, _ = _try_unique(page, xpath)
            if unique:
                return xpath

    # 4) Inputs by associated label
    try:
        label_text = el.evaluate(
            "(n) => {\n"
            "  function norm(s){return (s||'').replace(/\s+/g,' ').trim();}\n"
            "  if (n.id) {\n"
            "    const lbl = document.querySelector(`label[for=" + CSS.escape(n.id) + "]`);\n"
            "    if (lbl) return norm(lbl.innerText||lbl.textContent);\n"
            "  }\n"
            "  let p = n.parentElement;\n"
            "  while (p) {\n"
            "    if (p.tagName && p.tagName.toLowerCase()==='label') {\n"
            "      return norm(p.innerText||p.textContent);\n"
            "    }\n"
            "    p = p.parentElement;\n"
            "  }\n"
            "  return null;\n"
            "}"
        )
    except Exception:
        label_text = None
    if label_text:
        x = f"//{tag}[ancestor-or-self::*[self::label][normalize-space(.)={_escape_xpath_literal(_normalize_text(label_text))}]]"
        unique, _ = _try_unique(page, x)
        if unique:
            return x

    # 5) Tag + multiple attribute predicates
    attr_preds = _build_attribute_predicates({k: attrs.get(k) for k in CANDIDATE_ATTRS})
    if attr_preds:
        xpath = f"//{tag}[" + " and ".join(attr_preds) + "]"
        unique, count = _try_unique(page, xpath)
        if unique:
            return xpath
        # Try narrowing with text contains
        if text:
            xpath2 = xpath[:-1] + f" and contains(normalize-space(.), {_escape_xpath_literal(text[:40])})]"
            unique2, _ = _try_unique(page, xpath2)
            if unique2:
                return xpath2

    # 6) Ancestor with id or data-testid
    try:
        anc_info = el.evaluate(
            "(n)=>{\n"
            "  const pick = ['id','data-testid','data-test','data-qa','aria-label','role','class'];\n"
            "  function norm(s){return (s||'').replace(/\s+/g,' ').trim();}\n"
            "  let a = n.parentElement;\n"
            "  while (a){\n"
            "    const tag = a.tagName ? a.tagName.toLowerCase(): 'div';\n"
            "    const attrs = {};\n"
            "    for (const k of pick){ if (a.hasAttribute && a.hasAttribute(k)) attrs[k]=a.getAttribute(k); }\n"
            "    if (attrs.id || attrs['data-testid'] || attrs['data-test'] || attrs['data-qa']){\n"
            "      return {tag, attrs, text: norm(a.innerText||a.textContent)};\n"
            "    }\n"
            "    a = a.parentElement;\n"
            "  }\n"
            "  return null;\n"
            "}"
        )
    except Exception:
        anc_info = None
    if anc_info:
        a_tag = anc_info.get("tag", "*")
        a_attrs = anc_info.get("attrs", {})
        a_preds = _build_attribute_predicates(a_attrs)
        if a_preds:
            parent_xpath = f"//{a_tag}[" + " and ".join(a_preds) + "]"
            child_pred = ""
            if attr_preds:
                child_pred = "[" + " and ".join(attr_preds) + "]"
            elif text:
                child_pred = f"[contains(normalize-space(.), {_escape_xpath_literal(text[:40])})]"
            xpath = f"{parent_xpath}//{tag}{child_pred}"
            unique, _ = _try_unique(page, xpath)
            if unique:
                return xpath

    # 7) Fallback: positional index among same tag
    # Count index 1-based among siblings of same tag under body
    try:
        idx = el.evaluate(
            "(n)=>{\n"
            "  let i=0;\n"
            "  const tag = n.tagName.toLowerCase();\n"
            "  const nodes = Array.from(document.querySelectorAll(tag));\n"
            "  for (let k=0;k<nodes.length;k++){ if (nodes[k]===n) { return k+1; } }\n"
            "  return 1;\n"
            "}"
        )
    except Exception:
        idx = 1
    xpath = f"//{tag}[{idx}]"
    return xpath


def scan_interactables(page: Page) -> List[Dict[str, Any]]:
    selector = ", ".join(INTERACTABLE_CSS)
    els = page.query_selector_all(selector)
    results: List[Dict[str, Any]] = []
    for el in els:
        try:
            info = _get_element_basic_info(el)
            xpath = build_xpath_for_element(page, el)
            entry = {
                "tag": info.get("tag"),
                "text": _normalize_text(info.get("text")),
                "attributes": info.get("attrs"),
                "xpath": xpath,
            }
            results.append(entry)
        except Exception as e:
            # continue on individual element errors
            results.append({"error": str(e)})
    return results

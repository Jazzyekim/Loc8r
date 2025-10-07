from __future__ import annotations

import re
from typing import List, Dict, Any, Optional, Tuple

from playwright.sync_api import Page, ElementHandle


def _css_escape_value(val: str) -> str:
    # Minimal escaping for CSS attribute values: escape double quotes and backslashes
    return val.replace("\\", "\\\\").replace('"', '\\"')


def _build_css_attr_predicates(attrs: Dict[str, Optional[str]]) -> List[str]:
    preds: List[str] = []
    for k, v in attrs.items():
        if not v:
            continue
        if len(v) > 120:
            continue
        preds.append(f"[{k}=\"{_css_escape_value(v)}\"]")
    return preds


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


def _try_unique_css(page: Page, css: str) -> Tuple[bool, int]:
    try:
        matches = page.locator(css)
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
            "  function norm(s){return (s||'').replace(/\\s+/g,' ').trim();}\n"
            "  if (n.id) {\n"
            "    const labels = document.querySelectorAll('label[for]');\n"
            "    for (const lbl of labels) {\n"
            "      if (lbl.getAttribute('for') === n.id) {\n"
            "        return norm(lbl.innerText||lbl.textContent);\n"
            "      }\n"
            "    }\n"
            "  }\n"
            "  let p = n;\n"
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


def _css_selector_from_attrs(tag: str, attrs: Dict[str, Optional[str]]) -> str:
    preds = _build_css_attr_predicates(attrs)
    base = tag if tag else "*"
    if preds:
        return base + "".join(preds)
    return base


def build_css_for_element(page: Page, el: ElementHandle) -> str:
    info = _get_element_basic_info(el)
    tag = info.get("tag") or "*"
    attrs: Dict[str, str] = info.get("attrs") or {}

    # 1) id unique
    el_id = attrs.get("id")
    if el_id:
        simple = re.match(r"^[A-Za-z_][A-Za-z0-9\-\:_\.]*$", el_id or "") is not None
        css = f"#{el_id}" if simple else f"[id=\"{_css_escape_value(el_id)}\"]"
        unique, _ = _try_unique_css(page, css)
        if unique:
            return css

    # 2) strong attributes
    for strong in ["data-testid", "data-test", "data-qa", "name", "aria-label", "title"]:
        val = attrs.get(strong)
        if val:
            css = f"{tag}[{strong}=\"{_css_escape_value(val)}\"]"
            unique, _ = _try_unique_css(page, css)
            if unique:
                return css

    # 3) tag + multiple attrs
    cand = {k: attrs.get(k) for k in CANDIDATE_ATTRS}
    css = _css_selector_from_attrs(tag, cand)
    if css:
        unique, _ = _try_unique_css(page, css)
        if unique:
            return css

    # 4) with ancestor having stable id/data-testid
    try:
        anc = el.evaluate(
            "(n)=>{\n"
            "  const pick=['id','data-testid','data-test','data-qa'];\n"
            "  let a=n.parentElement;\n"
            "  while(a){\n"
            "    const attrs={};\n"
            "    for(const k of pick){ if(a.hasAttribute && a.hasAttribute(k)) attrs[k]=a.getAttribute(k); }\n"
            "    if(attrs.id||attrs['data-testid']||attrs['data-test']||attrs['data-qa']){\n"
            "      const tag=a.tagName?a.tagName.toLowerCase():'div';\n"
            "      return {tag, attrs};\n"
            "    }\n"
            "    a=a.parentElement;\n"
            "  }\n"
            "  return null;\n"
            "}"
        )
    except Exception:
        anc = None
    if anc:
        a_tag = anc.get("tag") or "*"
        a_sel = _css_selector_from_attrs(a_tag, anc.get("attrs") or {})
        child_sel = _css_selector_from_attrs(tag, cand)
        css2 = f"{a_sel} {child_sel}"
        unique, _ = _try_unique_css(page, css2)
        if unique:
            return css2

    # 5) fallback nth-of-type under nearest stable ancestor or body
    try:
        nth = el.evaluate(
            "(n)=>{\n"
            "  const p=n.parentElement;\n"
            "  if(!p) return {index:1, parent:null};\n"
            "  const tag=n.tagName.toLowerCase();\n"
            "  let c=0;\n"
            "  for(const ch of p.children){ if(ch.tagName && ch.tagName.toLowerCase()===tag){ c++; if(ch===n) return {index:c}; } }\n"
            "  return {index:1};\n"
            "}"
        )
    except Exception:
        nth = {"index": 1}
    idx = nth.get("index", 1)

    parent_css = "body"
    if anc:
        parent_css = _css_selector_from_attrs(anc.get("tag") or "*", anc.get("attrs") or {})
    css3 = f"{parent_css} > {tag}:nth-of-type({idx})"
    unique, _ = _try_unique_css(page, css3)
    if unique:
        return css3

    # last resort: just tag
    return tag


def _infer_role_and_name(page: Page, el: ElementHandle) -> Tuple[Optional[str], Optional[str]]:
    info = _get_element_basic_info(el)
    tag = info.get("tag") or "*"
    attrs: Dict[str, str] = info.get("attrs") or {}
    text = _normalize_text(info.get("text") or "")

    role = attrs.get("role")
    itype = (attrs.get("type") or "").lower()
    href = attrs.get("href")

    if not role:
        if tag == "button" or (tag == "input" and itype in {"button","submit","reset"}):
            role = "button"
        elif tag == "a" and href:
            role = "link"
        elif tag == "input" and itype == "checkbox":
            role = "checkbox"
        elif tag == "input" and itype == "radio":
            role = "radio"
        elif tag == "input" and itype in {"text","search","url","email","tel","password","number"}:
            role = "textbox"
        elif tag == "textarea":
            role = "textbox"
        elif tag == "select":
            role = "combobox"
        elif tag == "img":
            role = "img"
        elif attrs.get("tabindex") is not None:
            role = "generic"

    # name inference
    name: Optional[str] = attrs.get("aria-label") or attrs.get("title") or attrs.get("alt")
    if not name:
        # try associated label for form controls
        try:
            lbl = el.evaluate(
                "(n)=>{\n"
                "  function norm(s){return (s||'').replace(/\\s+/g,' ').trim();}\n"
                "  if(n.id){\n"
                "    const labels=document.querySelectorAll('label[for]');\n"
                "    for(const lb of labels){ if(lb.getAttribute('for')===n.id) return norm(lb.innerText||lb.textContent); }\n"
                "  }\n"
                "  let p=n; while(p){ if(p.tagName && p.tagName.toLowerCase()==='label') return norm(p.innerText||p.textContent); p=p.parentElement;}\n"
                "  return null;\n"
                "}"
            )
        except Exception:
            lbl = None
        if isinstance(lbl, str) and lbl.strip():
            name = _normalize_text(lbl)
    if not name and role in {"button","link"} and text:
        name = text

    return role, name


def build_role_locator_for_element(page: Page, el: ElementHandle) -> Optional[Dict[str, Any]]:
    role, name = _infer_role_and_name(page, el)
    if not role:
        return None
    try:
        loc = page.get_by_role(role, name=name) if name else page.get_by_role(role)
        count = loc.count()
        if count == 1:
            return {"role": role, "name": name}
    except Exception:
        pass
    return None


def scan_interactables(page: Page) -> List[Dict[str, Any]]:
    selector = ", ".join(INTERACTABLE_CSS)
    els = page.query_selector_all(selector)
    results: List[Dict[str, Any]] = []
    for el in els:
        try:
            info = _get_element_basic_info(el)
            xpath = build_xpath_for_element(page, el)
            css = build_css_for_element(page, el)
            role_loc = build_role_locator_for_element(page, el)
            attrs = info.get("attrs") or {}
            entry = {
                "tag": info.get("tag"),
                "text": _normalize_text(info.get("text")),
                "attributes": attrs,
                "id": attrs.get("id"),
                "xpath": xpath,
                "css": css,
                "role": role_loc,
            }
            results.append(entry)
        except Exception as e:
            results.append({"error": str(e)})
    return results

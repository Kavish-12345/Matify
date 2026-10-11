"""
The fixed requirement form that the chat fills.

The LLM can only call record_answer(field, value, user_words). This module
validates every value against the allowed options. The code (not the LLM)
decides when the form is complete.

Form value conventions
    None          -> not answered yet
    "not_sure"    -> user said they are not sure (allowed for every field)
    optional fields answered with "none": volume "not_sure", min_limits {}, include/avoid []
"""
from __future__ import annotations

import re

from backend.engine.options import FAMILIES, FIELDS, MIN_LIMIT_FIELDS

REQUIRED = ["part_name", "properties", "primary_property", "environment",
            "weight_priority", "cost_priority"]
OPTIONAL = ["volume_cm3", "min_limits", "include", "avoid"]
FIELD_ORDER = REQUIRED + OPTIONAL

_NONE_WORDS = {"not_sure", "not sure", "none", "no", "skip", "nothing", "na", "n/a", "no limits", "dont know", "don't know"}


def empty_form() -> dict:
    form = {f: None for f in FIELD_ORDER}
    form["user_words"] = {}
    form["suggested"] = []   # AI suggestions for 'properties' (shown pre-ticked; never counted until confirmed)
    return form


def normalise_form(form: dict | None) -> dict:
    base = empty_form()
    if form:
        for k in FIELD_ORDER:
            if k in form:
                base[k] = form[k]
        base["user_words"] = dict(form.get("user_words") or {})
        base["suggested"] = list(form.get("suggested") or [])
    return base


def missing_fields(form: dict) -> list[str]:
    return [f for f in FIELD_ORDER if form.get(f) is None]


def _is_none_word(v: str) -> bool:
    return v.strip().lower().replace("_", " ") in {w.replace("_", " ") for w in _NONE_WORDS}


def _split(value) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [v.strip() for v in re.split(r"[,;]", str(value)) if v.strip()]


def _match_classes(vals: list[str], classes: list[str]) -> tuple[list[str], list[str]]:
    lookup = {c.lower(): c for c in classes}
    good, bad = [], []
    for v in vals:
        c = lookup.get(v.strip().lower())
        (good if c else bad).append(c or v)
    return good, bad


def apply_answer(form: dict, field: str, value, user_words: str, groups: list[str],
                 classes: list[str] | None = None) -> str | None:
    """Validate and store one answer. Returns an error message, or None if recorded."""
    classes = classes or []
    if field == "suggested_properties":  # AI hint only: pre-ticks the card, user must confirm
        good, _ = _match_classes(_split(value or ""), classes)
        form["suggested"] = good
        return None
    if field not in FIELD_ORDER:
        return f"Unknown field '{field}'. Valid fields: {', '.join(FIELD_ORDER)}"
    raw = "" if value is None else value
    text = raw if isinstance(raw, str) else str(raw)

    if field == "part_name":
        if not text.strip():
            return "part_name must not be empty"
        form[field] = text.strip()[:80]

    elif field == "properties":
        vals = _split(raw)
        if not vals or (len(vals) == 1 and _is_none_word(vals[0])):
            form["properties"], form["primary_property"] = ["not_sure"], "not_sure"
        else:
            good, bad = _match_classes([v for v in vals if not _is_none_word(v)], classes)
            if bad or not good:
                return f"Unknown property {bad}. Allowed: {', '.join(classes)}"
            form["properties"] = good
            # one class -> it is the most important; several -> ask which one matters most
            if len(good) == 1:
                form["primary_property"] = good[0]
            elif form.get("primary_property") not in good:
                form["primary_property"] = None

    elif field == "primary_property":
        chosen = [p for p in (form.get("properties") or []) if p != "not_sure"]
        if _is_none_word(text):
            form[field] = "not_sure"
        else:
            good, _ = _match_classes([text], chosen)
            if not good:
                return f"primary_property must be one of the chosen properties: {', '.join(chosen) or 'none chosen yet'}"
            form[field] = good[0]

    elif field in ("environment", "weight_priority", "cost_priority"):
        v = text.strip()
        if v not in FIELDS[field]:
            return f"Invalid {field} '{v}'. Allowed: {', '.join(FIELDS[field])}"
        form[field] = v

    elif field == "volume_cm3":
        if _is_none_word(text):
            form[field] = "not_sure"
        else:
            m = re.search(r"\d+(?:\.\d+)?", text)
            if not m or float(m.group()) <= 0:
                return "volume_cm3 must be a positive number in cm3, or 'not_sure'"
            form[field] = float(m.group())

    elif field == "min_limits":
        if isinstance(raw, dict):
            pairs = [(k, raw[k]) for k in raw]
        elif _is_none_word(text):
            pairs = []
        else:
            pairs = re.findall(r"([A-Za-z_]+)\s*[=:>]+\s*(\d+(?:\.\d+)?)", text)
            if not pairs:
                return "min_limits format: 'Sy=400, Su=600, A5=10, E=70000, Ro_max=3000' or 'none'"
        out = {}
        for k, v in pairs:
            if k not in MIN_LIMIT_FIELDS:
                return f"Unknown limit '{k}'. Allowed: {', '.join(MIN_LIMIT_FIELDS)}"
            out[k] = float(v)
        err = check_limit_units(out)
        if err:
            return err
        form[field] = out

    elif field in ("include", "avoid"):
        if isinstance(raw, list):
            vals = _split(raw)
        elif _is_none_word(text):
            vals = []
        else:
            vals = _split(raw)
        bad = [v for v in vals if v not in groups]
        if bad:
            return f"Unknown material group(s) {bad}. Allowed: {', '.join(groups)}"
        other = form.get("avoid" if field == "include" else "include") or []
        clash = [v for v in vals if v in other]
        if clash:
            return (f"{clash} is already in '{'avoid' if field == 'include' else 'include'}'. "
                    "A group cannot be both included and avoided; ask the user which one they mean.")
        form[field] = vals

    if user_words:
        form["user_words"][field] = str(user_words)[:200]
    return None


def check_limit_units(lim: dict) -> str | None:
    """Catch common unit mistakes before they silently empty the result list."""
    if "Ro_max" in lim and lim["Ro_max"] < 100:
        return (f"Max density {lim['Ro_max']:g} looks like g/cm3. Density must be in kg/m3 "
                f"(e.g. {lim['Ro_max'] * 1000:g} kg/m3; steel is about 7850, aluminium about 2700).")
    if "Ro_max" in lim and lim["Ro_max"] < 1700:
        return (f"Max density {lim['Ro_max']:g} kg/m3 is lighter than every metal in the dataset "
                "(the lightest, magnesium, is about 1,740 kg/m3; aluminium about 2,700).")
    if "E" in lim and lim["E"] < 1000:
        return (f"E = {lim['E']:g} looks like GPa. E must be in MPa "
                f"(e.g. {lim['E'] * 1000:g} MPa; steel is about 210000).")
    for k in ("Su", "Sy"):
        if k in lim and lim[k] > 3000:
            return f"{k} = {lim[k]:g} MPa is higher than any material in the dataset (about 2000 MPa max)."
    if "A5" in lim and lim["A5"] > 80:
        return f"Elongation A5 = {lim['A5']:g}% is unrealistically high (typical metals 1-60%)."
    return None


def to_recommend_payload(form: dict, price_overrides: dict | None = None, top_n: int = 10) -> dict:
    """Convert the chat form into the /api/recommend request (same one the No-AI form sends)."""
    vol = form.get("volume_cm3")
    return {
        "part_name": form.get("part_name"),
        "properties": form.get("properties") or ["not_sure"],
        "primary_property": form.get("primary_property") if form.get("primary_property") != "not_sure" else None,
        "environment": form.get("environment") or "not_sure",
        "weight_priority": form.get("weight_priority") or "not_sure",
        "cost_priority": form.get("cost_priority") or "not_sure",
        "volume_cm3": vol if isinstance(vol, (int, float)) else None,
        "min_limits": form.get("min_limits") if isinstance(form.get("min_limits"), dict) else {},
        "include": form.get("include") if isinstance(form.get("include"), list) else [],
        "avoid": form.get("avoid") if isinstance(form.get("avoid"), list) else [],
        "price_overrides": price_overrides or {},
        "top_n": top_n,
    }


def allowed_groups(price_categories: dict) -> list[str]:
    return list(FAMILIES) + list(price_categories)

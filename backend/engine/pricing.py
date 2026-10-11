"""
Price layer: maps every dataset row to a price category and computes cost.

Prices live in backend/data/prices.json (static, dated, sourced). The user can
override any category price per request.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

PRICES_PATH = Path(__file__).resolve().parents[1] / "data" / "prices.json"


def load_prices(path: Path = PRICES_PATH) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# Row -> price category
# --------------------------------------------------------------------------
_PREFIXES = re.compile(r"\b(steel|gost|din|en|nf|bs|jis|csn|iso|ansi|sae|aisi)\b")


def _is_alloy_steel(name: str) -> bool:
    n = name.lower()
    m = re.search(r"\b(?:sae|aisi)\s*(\d)(\d)\d\d\b", n)
    if m:
        return m.group(1) in "23456789"
    m = re.search(r"\bcsn\s*1([3-6])\d{3}", n)
    if m:
        return True
    m = re.search(r"\bbs\s*([5-9])\d\d[a-z]\d", n)
    if m:
        return True
    core = _PREFIXES.sub(" ", n)
    core = re.sub(r"\d{3,4}-\d{2}", " ", core)  # GOST standard numbers
    return bool(re.search(r"(cr|mo|ni|ch|ncd|\dcd|scm|snc|\dv)", core))


def _stainless_kind(name: str) -> str:
    n = name.lower().replace(" ", "")
    if re.search(r"316|317|nimo|17346|17347|17348|17349", n):
        return "stainless_mo"
    if re.search(r"(sus|aisi|sae|^)4[0-4]\d|x\d+cr\d+(?!ni)$|x\d+cr1[37]$|1702\d|1704\d", n) and "ni" not in n:
        return "stainless_ferritic"
    return "stainless_austenitic"


def _copper_category(name: str, desc: str) -> str:
    n = name.lower()
    m = re.search(r"\bc(\d{5})\b", n)
    if m:
        u = int(m.group(1))
        if 17000 <= u < 18000 or 82000 <= u < 83000:
            return "beryllium_copper"
        if u < 20000 or 80000 <= u < 82000:
            return "copper"
        if u < 50000 or 83000 <= u < 86000 or 87200 <= u < 87300:
            return "brass"
        if 70000 <= u < 80000 or 96000 <= u < 98000:
            return "copper_nickel"
        return "bronze"
    text = f"{n} {desc.lower()}"
    if "brass" in text or re.search(r"\b4230\d\d", n) or re.search(r"\b4232\d\d", n):
        return "brass"
    return "bronze"


def price_category(row: pd.Series) -> str:
    fam = row["family"]
    name = str(row["Material"])
    desc = "" if pd.isna(row.get("Desc")) else str(row["Desc"])
    labels = str(row.get("app_classes", ""))
    n, d = name.lower(), desc.lower()

    if fam == "aluminium":
        grp = str(row.get("group", n))
        if re.search(r"\d{3}\.\d", grp) or ("csn" in grp and "Castings" in labels):
            return "aluminium_cast"
        if re.search(r"\b[27]\d{3}\b", grp):
            return "aluminium_high_strength"
        return "aluminium_wrought"
    if fam == "copper":
        return _copper_category(name, desc)
    if fam == "magnesium":
        code = n.replace("magnesium alloy", "").strip()
        return "magnesium_re" if re.match(r"(we|ez|qe|ze|hk|hm|hz|qh|zh|ek)", code) else "magnesium_alloy"

    # ---- ferrous ----
    text = f"{n} {d}"
    if "cast iron" in text or re.search(r"\bggg|\bgg\s*-?\s*\d|\bgt[swb]", n):
        if any(k in text for k in ("nodular", "malleable", "ductile", "ggg", "gts", "gtw", "gtb")):
            return "ductile_iron"
        return "grey_cast_iron"
    if "cast steel" in d:
        return "stainless_cast" if "corrosion" in d else "cast_steel"
    if "heat-resist" in d or "heat resist" in d or "high-temperature" in d:
        return "heat_resistant_steel"
    if "stainless" in d or "corrosion" in d or re.search(r"\bsus\d|\bsae\s*30\d{3}|\bx\d+crni", n):
        return _stainless_kind(name)
    if "spring" in d:
        return "spring_steel"
    if "free-cutting" in d or "machinability" in d or re.search(r"\b(?:sae|aisi)\s*1[12]\d\d\b|\bsum\d", n):
        return "free_cutting_steel"
    return "alloy_steel" if _is_alloy_steel(name) else "carbon_steel"


# --------------------------------------------------------------------------
# Price lookup and cost
# --------------------------------------------------------------------------
def effective_prices(prices: dict, overrides: dict | None = None) -> dict[str, dict]:
    """Category -> {price, source, date, overridden}."""
    out = {}
    for key, c in prices["categories"].items():
        out[key] = {
            "price": float(c["price"]),
            "source": c["source"],
            "url": c.get("url", ""),
            "basis": c["basis"],
            "date": prices["retrieved_on"],
            "overridden": False,
        }
    for key, value in (overrides or {}).items():
        if key in out and value is not None and float(value) > 0:
            out[key].update(price=float(value), source="Custom price entered by user",
                            url="", basis="custom", overridden=True)
    return out


def cost_per_part(price_rs_kg: float, density_kg_m3: float, volume_cm3: float | None) -> float | None:
    """Rs per part = price (Rs/kg) x density (kg/m3) x volume (m3). Material cost only."""
    if not volume_cm3:
        return None
    return price_rs_kg * density_kg_m3 * volume_cm3 * 1e-6

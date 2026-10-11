"""
Recommendation engine.

form -> target classes + weights -> filter -> ML suitability -> price -> TOPSIS
     -> ranked results with a "Why this material?" breakdown.

The ML model makes the selection signal (suitability). No LLM is involved here;
the chat and the No-AI form both call this same function.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .options import FAMILIES, FIELDS, MIN_LIMIT_FIELDS, PRIORITY_WEIGHT, target_classes, topsis_weights
from .preprocess import build_X, clean
from .pricing import cost_value, effective_prices, load_prices, price_category
from .topsis import topsis

BACKEND = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND / "data"
MODEL_DIR = BACKEND / "models"


# --------------------------------------------------------------------------
# Loading (once per process)
# --------------------------------------------------------------------------
def _proba(model, X) -> np.ndarray:
    P = model.predict_proba(X)
    if isinstance(P, list):
        clf = model[-1] if hasattr(model, "steps") else model
        cols = []
        for p, cls in zip(P, clf.classes_):
            cls = list(cls)
            cols.append(p[:, cls.index(1)] if 1 in cls else np.zeros(len(X)))
        return np.column_stack(cols)
    return np.asarray(P)


@lru_cache(maxsize=1)
def load_engine():
    meta = json.loads((MODEL_DIR / "model_meta.json").read_text())
    model = joblib.load(MODEL_DIR / "suitability_model.joblib")
    mlb = joblib.load(MODEL_DIR / "label_binarizer.joblib")
    prices = load_prices()

    raw = pd.read_csv(DATA_DIR / "Data_labelled.csv")
    df, _ = clean(raw, a5_medians=meta["a5_medians"])
    df = df[df["status"] != "exclude"].reset_index(drop=True)  # out of scope (conductors etc.)

    P = _proba(model, build_X(df, meta["features"]))
    classes = list(mlb.classes_)
    for i, c in enumerate(classes):
        df[f"p::{c}"] = P[:, i]

    df["price_category"] = df.apply(price_category, axis=1)
    cats = prices["categories"]
    df["corrosion_score"] = df["price_category"].map(lambda k: cats[k]["corrosion_score"])
    df["display_name"] = [
        f"{m}" + (f" ({h})" if isinstance(h, str) and h.strip() else "")
        for m, h in zip(df["Material"], df["Heat treatment"])
    ]
    return {"meta": meta, "df": df, "classes": classes, "prices": prices}


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------
def validate_form(form: dict, prices: dict) -> dict:
    """Return a cleaned copy; raise ValueError with a clear message on bad input."""
    f = dict(form)
    funcs = f.get("function") or ["not_sure"]
    if isinstance(funcs, str):
        funcs = [funcs]
    for v in funcs:
        if v not in FIELDS["function"]:
            raise ValueError(f"function: unknown option '{v}'")
    f["function"] = funcs
    for field in ("loading", "environment", "manufacturing", "weight_priority", "cost_priority"):
        v = f.get(field) or "not_sure"
        if v not in FIELDS[field]:
            raise ValueError(f"{field}: unknown option '{v}'")
        f[field] = v
    vol = f.get("volume_cm3")
    f["volume_cm3"] = float(vol) if vol not in (None, "", 0) else None
    if f["volume_cm3"] is not None and f["volume_cm3"] <= 0:
        raise ValueError("volume_cm3 must be positive")
    limits = {k: float(v) for k, v in (f.get("min_limits") or {}).items() if v not in (None, "")}
    for k in limits:
        if k not in MIN_LIMIT_FIELDS:
            raise ValueError(f"min_limits: unknown field '{k}'")
    f["min_limits"] = limits
    groups = set(FAMILIES) | set(prices["categories"])
    for key in ("include", "avoid"):
        vals = f.get(key) or []
        bad = [v for v in vals if v not in groups]
        if bad:
            raise ValueError(f"{key}: unknown material group(s) {bad}")
        f[key] = list(vals)
    f["price_overrides"] = {k: float(v) for k, v in (f.get("price_overrides") or {}).items()
                            if k in prices["categories"] and v not in (None, "")}
    f["top_n"] = int(f.get("top_n") or 10)
    return f


# --------------------------------------------------------------------------
# Main entry
# --------------------------------------------------------------------------
def recommend(form: dict) -> dict:
    eng = load_engine()
    df, prices = eng["df"], eng["prices"]
    form = validate_form(form, prices)

    targets = target_classes(form)
    raw_w = topsis_weights(form)

    # 1. Filter: hard limits and include / avoid
    cand = df
    lim = form["min_limits"]
    for col in ("Su", "Sy", "A5", "E"):
        if col in lim:
            cand = cand[cand[col] >= lim[col]]
    if "Ro_max" in lim:
        cand = cand[cand["Ro"] <= lim["Ro_max"]]
    in_group = lambda vals: cand["family"].isin(vals) | cand["price_category"].isin(vals)
    if form["include"]:
        cand = cand[in_group(form["include"])]
    if form["avoid"]:
        cand = cand[~in_group(form["avoid"])]
    n_after_filter = len(cand)
    if cand.empty:
        return {"form": form, "targets": targets, "weights": raw_w, "results": [],
                "n_candidates": 0, "message": "No material meets the limits. Relax a limit or the include/avoid list."}
    cand = cand.copy()

    # 2. ML suitability = importance-weighted mean probability of the target classes
    tw = np.array(list(targets.values()), dtype=float)
    P = cand[[f"p::{c}" for c in targets]].to_numpy()
    cand["suitability"] = (P * tw).sum(axis=1) / tw.sum()

    # 3. Price layer: cited range per group; ranking uses the midpoint
    eff = effective_prices(prices, form["price_overrides"])
    vol = form["volume_cm3"]
    g = cand["price_category"]
    for k in ("low", "typical", "high"):
        cand[f"cost_{k}"] = [cost_value(eff[c][k], r, vol) for c, r in zip(g, cand["Ro"])]
    cand["price_available"] = g.map(lambda c: eff[c]["available"])

    # 4. One row per alloy: keep its most suitable heat-treatment condition
    cand = (cand.sort_values(["suitability", "cost_typical"], ascending=[False, True], na_position="last")
                .drop_duplicates("group", keep="first"))

    # Materials with no price: ranked as the most expensive candidate (conservative) and flagged
    known = cand["cost_typical"].dropna()
    fill = float(known.max()) if len(known) else 1.0
    cand["cost_rank_value"] = cand["cost_typical"].fillna(fill)

    # 5. TOPSIS over distinct alloys
    crit = ["suitability", "cost_rank_value", "Ro", "corrosion_score"]
    w = np.array([raw_w["suitability"], raw_w["cost"], raw_w["density"], raw_w["corrosion"]], dtype=float)
    benefit = np.array([True, False, False, True])
    cand["topsis"] = topsis(cand[crit].to_numpy(dtype=float), w, benefit)
    cand = cand.sort_values(["topsis", "suitability"], ascending=False)

    top = cand.head(form["top_n"])
    ref = top.iloc[0]["cost_typical"]  # #1's typical cost, for the comparison label
    results = [_explain(row, rank, targets, eff, vol, ref) for rank, (_, row) in enumerate(top.iterrows(), start=1)]
    return {
        "form": form,
        "targets": targets,
        "weights": raw_w,
        "weights_normalised": dict(zip(["suitability", "cost", "density", "corrosion"], (w / w.sum()).round(3).tolist())),
        "cost_basis": "Rs per part" if vol else "Rs per cm3 of material (enter a part volume for Rs per part)",
        "n_candidates": int(n_after_filter),
        "n_alloys_ranked": int(len(cand)),
        "results": results,
        "note": "TOPSIS scores are relative to the candidate set; changing the set can change the order (rank reversal).",
    }


def _compare(cost, ref, rank):
    if rank == 1:
        return "Top-ranked material (reference)"
    if cost is None or ref is None or pd.isna(cost) or pd.isna(ref) or ref == 0:
        return "Cannot compare (price not available)"
    r = cost / ref
    if 0.9 <= r <= 1.1:
        return "Similar cost to #1"
    return f"About {r:.1f}x the cost of #1" if r > 1 else f"About {r:.1f}x the cost of #1 (cheaper)"


def _explain(row, rank, targets, eff, vol, ref) -> dict:
    cat = row["price_category"]
    price = eff[cat]
    class_probs = {c: round(float(row[f"p::{c}"]) * 100, 1) for c in targets}
    unit = "per part" if vol else "per cm3"
    if price["available"]:
        lo, hi = float(row["cost_low"]), float(row["cost_high"])
        dec = 2 if hi < 10 else 0
        cost_text = (f"Rs {lo:.{dec}f} {unit} (your price)" if price["custom"]
                     else f"Rs {lo:.{dec}f} - {hi:.{dec}f} {unit}")
        price_text = (f"Rs {price['low']:.0f}/kg (your price)" if price["custom"]
                      else f"Rs {price['low']:.0f} - {price['high']:.0f}/kg")
    else:
        cost_text = price_text = "Price not available - enter your price"
    why = [f"{c}: model suitability {p:.0f}%" for c, p in sorted(class_probs.items(), key=lambda x: -x[1])]
    why.append(f"Density {row['Ro']:.0f} kg/m³, corrosion score {int(row['corrosion_score'])}/5")
    return {
        "rank": rank,
        "material": row["Material"],
        "heat_treatment": None if pd.isna(row["Heat treatment"]) else row["Heat treatment"],
        "display_name": row["display_name"],
        "standard": row["Std"],
        "family": row["family"],
        "material_group": cat,
        "material_group_label": price["label"],
        "suitability_pct": round(float(row["suitability"]) * 100, 1),
        "class_suitability_pct": class_probs,
        "topsis_score": round(float(row["topsis"]), 4),
        "properties": {k: (None if pd.isna(row[k]) else round(float(row[k]), 3)) for k in ("Su", "Sy", "A5", "E", "G", "mu", "Ro")},
        "a5_imputed": bool(row["A5_imputed"]),
        "price": {
            "available": price["available"],
            "custom": price["custom"],
            "rs_per_kg_low": price["low"],
            "rs_per_kg_high": price["high"],
            "text": price_text,
            "basis": price["basis"],
            "source": price["source"],
            "url": price["url"],
            "date": price["date"],
            "why": price["why"],
        },
        "cost": {
            "unit": unit,
            "low": None if pd.isna(row["cost_low"]) else round(float(row["cost_low"]), 2),
            "high": None if pd.isna(row["cost_high"]) else round(float(row["cost_high"]), 2),
            "text": cost_text,
            "vs_top": _compare(row["cost_typical"], ref, rank),
        },
        "corrosion_score": int(row["corrosion_score"]),
        "labelled_classes": row["app_classes"] if row["status"] == "train" else "(no label; scored by model)",
        "why": why,
    }

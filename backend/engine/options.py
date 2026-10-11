"""
Fixed requirement form: allowed options and the answer -> class / weight mapping.

The chat (LLM) and the No-AI form both fill exactly these fields. Every field
accepts "not_sure". The code, not the LLM, turns answers into ML target classes
and TOPSIS weights.
"""
from __future__ import annotations

PRIORITY_WEIGHT = {"critical": 3, "important": 2, "not_important": 0, "not_sure": 1}

FAMILIES = ["ferrous", "aluminium", "copper", "magnesium"]

# field -> option -> {label, classes: {class: importance}, ...}
FIELDS = {
    "function": {  # multi-select
        "load_bearing":     {"label": "Carries load (frame, bracket, beam)", "classes": {"Structural": 3}},
        "rotating_or_gear": {"label": "Rotating part / shaft / gear",        "classes": {"Heat-treatable": 3, "Structural": 2}},
        "rubs_or_slides":   {"label": "Rubs or slides against another part", "classes": {"Wear-resistant": 3}},
        "springs_back":     {"label": "Must flex and spring back",           "classes": {"Spring": 3}},
        "fluid_contact":    {"label": "In contact with water or fluids",     "classes": {"Corrosion-resistant": 2}},
        "housing_or_cover": {"label": "Housing, casing or cover",            "classes": {"Structural": 2}},
        "not_sure":         {"label": "Not sure",                            "classes": {}},
    },
    "loading": {  # secondary signal: function decides the main classes
        "light_static": {"label": "Light, steady load",           "classes": {"Structural": 1}},
        "heavy_static": {"label": "Heavy, steady load",           "classes": {"Structural": 2, "Heat-treatable": 1}},
        "cyclic":       {"label": "Repeated / fluctuating load (fatigue)", "classes": {"Heat-treatable": 1, "Structural": 1}},
        "impact":       {"label": "Shock or impact",              "classes": {"Structural": 2, "Heat-treatable": 1}},
        "not_sure":     {"label": "Not sure",                     "classes": {}},
    },
    "environment": {
        "dry_indoor":       {"label": "Dry, indoors",             "classes": {},                          "corrosion_weight": 0},
        "outdoor_humid":    {"label": "Outdoors / humid",         "classes": {"Corrosion-resistant": 2},  "corrosion_weight": 2},
        "water_marine":     {"label": "Water or sea water",       "classes": {"Corrosion-resistant": 3},  "corrosion_weight": 3},
        "chemical":         {"label": "Chemicals / acids",        "classes": {"Corrosion-resistant": 3},  "corrosion_weight": 3},
        "high_temperature": {"label": "High temperature (> 300 °C)", "classes": {"Heat-resistant": 3},    "corrosion_weight": 1},
        "not_sure":         {"label": "Not sure",                 "classes": {},                          "corrosion_weight": 1},
    },
    "manufacturing": {
        "machining":      {"label": "Machined from bar/plate",    "classes": {}},
        "casting":        {"label": "Cast in a mould",            "classes": {"Castings": 3}},
        "sheet_forming":  {"label": "Bent / stamped from sheet",  "classes": {"Sheet forming": 3}},
        "forging":        {"label": "Forged",                     "classes": {"Heat-treatable": 2}},
        "bulk_machining": {"label": "Machined in large numbers (screws, fittings)", "classes": {"Free-machining": 3}},
        "not_sure":       {"label": "Not sure",                   "classes": {}},
    },
    "weight_priority": {k: {"label": k.replace("_", " ").capitalize()} for k in PRIORITY_WEIGHT},
    "cost_priority":   {k: {"label": k.replace("_", " ").capitalize()} for k in PRIORITY_WEIGHT},
}

MIN_LIMIT_FIELDS = {
    "Su": "Min tensile strength (MPa)",
    "Sy": "Min yield strength (MPa)",
    "A5": "Min elongation (%)",
    "E": "Min Young's modulus (MPa)",
    "Ro_max": "Max density (kg/m³)",
}

DEFAULT_CLASSES = {"Structural": 2}  # used when the answers give no class at all


def target_classes(form: dict) -> dict[str, int]:
    """Combine all answers into {class: importance 1-3}, keeping the highest importance."""
    out: dict[str, int] = {}

    def add(classes):
        for c, w in classes.items():
            out[c] = max(out.get(c, 0), w)

    for f in form.get("function") or ["not_sure"]:
        add(FIELDS["function"][f]["classes"])
    for field in ("loading", "environment", "manufacturing"):
        add(FIELDS[field][form.get(field, "not_sure")]["classes"])
    return out or dict(DEFAULT_CLASSES)


def topsis_weights(form: dict) -> dict[str, float]:
    """Raw criterion weights. Suitability is always the highest weight."""
    cost = PRIORITY_WEIGHT[form.get("cost_priority", "not_sure")]
    weight = PRIORITY_WEIGHT[form.get("weight_priority", "not_sure")]
    corr = FIELDS["environment"][form.get("environment", "not_sure")]["corrosion_weight"]
    suit = max(cost, weight, corr, 2) + 1
    return {"suitability": suit, "cost": cost, "density": weight, "corrosion": corr}


def options_payload(price_categories: dict) -> dict:
    """What GET /api/options returns (used by the React form and the chat validator)."""
    return {
        "fields": {f: [{"value": k, "label": v["label"]} for k, v in opts.items()] for f, opts in FIELDS.items()},
        "multi_select": ["function"],
        "min_limits": MIN_LIMIT_FIELDS,
        "families": FAMILIES,
        "material_groups": {k: v["label"] for k, v in price_categories.items()},
        "priority_weight": PRIORITY_WEIGHT,
    }

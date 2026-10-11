"""Run:  python -m pytest backend/tests -q"""
import numpy as np
import pytest

from backend.engine.recommend import load_engine, recommend
from backend.engine.topsis import topsis

BASE = dict(properties=["Structural"], environment="dry_indoor",
            weight_priority="important", cost_priority="important")


def test_topsis_simple():
    # A dominates B on both criteria -> A scores higher
    m = np.array([[0.9, 100.0], [0.5, 200.0]])
    s = topsis(m, np.array([1, 1]), np.array([True, False]))
    assert s[0] > s[1] and s[0] == pytest.approx(1.0)


def test_every_row_has_price_category():
    df = load_engine()["df"]
    assert df["price_category"].notna().all()
    assert len(df) == 1552 - 26  # EXCLUDE rows removed


def test_recommend_returns_ranked_results():
    res = recommend(BASE)
    r = res["results"]
    assert len(r) == 10
    assert [x["rank"] for x in r] == list(range(1, 11))
    scores = [x["topsis_score"] for x in r]
    assert scores == sorted(scores, reverse=True)
    assert len({x["material"] for x in r}) == 10  # one entry per alloy


def test_same_form_same_answer():  # No-AI form and chat must give identical results
    assert recommend(BASE)["results"] == recommend(dict(BASE))["results"]


def test_limits_and_avoid():
    res = recommend({**BASE, "min_limits": {"Sy": 600}, "avoid": ["ferrous"]})
    for x in res["results"]:
        assert x["properties"]["Sy"] >= 600 and x["family"] != "ferrous"


def test_price_range_and_override():
    a = recommend({**BASE, "volume_cm3": 100, "include": ["carbon_steel"], "top_n": 1})["results"][0]
    assert a["cost"]["low"] < a["cost"]["high"] and not a["price"]["custom"]
    b = recommend({**BASE, "volume_cm3": 100, "include": ["carbon_steel"], "top_n": 1,
                   "price_overrides": {"carbon_steel": 100}})["results"][0]
    assert b["price"]["custom"] and b["cost"]["low"] == b["cost"]["high"]
    assert b["cost"]["low"] == pytest.approx(100 * b["properties"]["Ro"] * 100e-6, rel=1e-3)


def test_table_not_changed_by_override():
    recommend({**BASE, "price_overrides": {"carbon_steel": 999}})
    assert load_engine()["prices"]["categories"]["carbon_steel"]["low"] == 52


def test_bad_option_rejected():
    with pytest.raises(ValueError):
        recommend({**BASE, "environment": "on_mars"})


def test_properties_come_from_model():
    from backend.engine.options import options_payload
    eng = load_engine()
    opts = options_payload(eng["prices"]["categories"], eng["classes"])
    assert [o["value"] for o in opts["fields"]["properties"]] == eng["classes"]


def test_primary_property_weighting_and_not_sure():
    a = recommend({**BASE, "properties": ["Wear-resistant", "Corrosion-resistant"], "primary_property": "Wear-resistant"})
    assert a["targets"] == {"Wear-resistant": 3, "Corrosion-resistant": 2}
    b = recommend({**BASE, "properties": ["not_sure"]})
    assert b["targets"] == {} and len(b["results"]) == 10   # best fit over all classes

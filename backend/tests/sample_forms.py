"""
Sample "professor queries" with the material groups we expect near the top.
Run:  python -m backend.tests.sample_forms
Prints the top 5 for each query and PASS / CHECK against expectations.
CHECK is not an error: it means a teammate should look at the result.
"""
from backend.engine.recommend import recommend

QUERIES = [
    ("Gear shaft (hardened, machined)",
     dict(properties=["Heat-treatable", "Structural"], primary_property="Heat-treatable", environment="dry_indoor",
          weight_priority="not_important", cost_priority="important"),
     {"alloy_steel", "carbon_steel"}),
    ("Compression spring",
     dict(properties=["Spring"], environment="dry_indoor", weight_priority="not_important", cost_priority="important"),
     {"spring_steel", "alloy_steel", "beryllium_copper", "bronze", "stainless_austenitic"}),
    ("Marine pump housing (cast)",
     dict(properties=["Castings", "Corrosion-resistant"], primary_property="Corrosion-resistant",
          environment="water_marine", weight_priority="not_sure", cost_priority="important"),
     {"bronze", "stainless_cast", "aluminium_cast", "copper_nickel", "brass"}),
    ("Lightweight aerospace bracket",
     dict(properties=["Structural", "Heat-treatable"], primary_property="Structural", environment="dry_indoor",
          weight_priority="critical", cost_priority="not_important"),
     {"aluminium_high_strength", "aluminium_wrought", "magnesium_alloy", "magnesium_re"}),
    ("Car body panel",
     dict(properties=["Sheet forming", "Corrosion-resistant"], primary_property="Sheet forming",
          environment="outdoor_humid", weight_priority="important", cost_priority="critical"),
     {"carbon_steel", "aluminium_wrought", "stainless_austenitic"}),
    ("Sliding bushing",
     dict(properties=["Wear-resistant"], environment="not_sure", weight_priority="not_important", cost_priority="important"),
     {"bronze", "alloy_steel", "carbon_steel", "grey_cast_iron", "brass"}),
    ("Exhaust manifold",
     dict(properties=["Heat-resistant", "Castings"], primary_property="Heat-resistant", environment="high_temperature",
          weight_priority="not_important", cost_priority="important"),
     {"heat_resistant_steel", "grey_cast_iron", "ductile_iron", "cast_steel", "stainless_cast"}),
    ("Screws made in bulk",
     dict(properties=["Free-machining", "Structural"], primary_property="Free-machining", environment="dry_indoor",
          weight_priority="not_important", cost_priority="critical"),
     {"free_cutting_steel", "brass", "carbon_steel"}),
    ("Chemical tank fitting (aluminium avoided)",
     dict(properties=["Corrosion-resistant"], environment="chemical", weight_priority="not_sure",
          cost_priority="not_important", avoid=["aluminium"]),
     {"stainless_mo", "stainless_austenitic", "copper_nickel", "bronze"}),
    ("Bracket, Sy >= 500 MPa, 150 cm3",
     dict(properties=["Structural"], environment="dry_indoor", weight_priority="important", cost_priority="important",
          volume_cm3=150, min_limits={"Sy": 500}),
     {"alloy_steel", "carbon_steel", "aluminium_high_strength"}),
]


def main():
    for title, form, expected in QUERIES:
        res = recommend(form)
        top = res["results"][:5]
        groups = {r["material_group"] for r in top}
        status = "PASS " if groups & expected else "CHECK"
        print(f"\n[{status}] {title}   targets={res['targets']}   weights={res['weights_normalised']}")
        for r in top:
            print(f"  {r['rank']}. {r['display_name'][:42]:42s} {r['material_group']:22s} "
                  f"suit {r['suitability_pct']:5.1f}%  topsis {r['topsis_score']:.3f}  "
                  f"{r['cost']['text']:28s} {r['cost']['vs_top']}")


if __name__ == "__main__":
    main()

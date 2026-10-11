import { useState } from "react";

const PROPS = [
  ["Su", "Tensile strength", "MPa"],
  ["Sy", "Yield strength", "MPa"],
  ["A5", "Elongation", "%"],
  ["E", "Young's modulus", "MPa"],
  ["Ro", "Density", "kg/m³"],
  ["mu", "Poisson's ratio", ""],
];

const BASIS = { market: "Market", listing: "Listing", custom: "Your price", not_available: "No price" };

export default function ResultCard({ r, onOverride }) {
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [price, setPrice] = useState("");

  const applyPrice = () => {
    if (price) onOverride(r.material_group, price);
    setEditing(false);
    setPrice("");
  };

  return (
    <article className={`card ${r.rank === 1 ? "best" : ""}`}>
      <div className="card-top">
        <div className="rank">#{r.rank}</div>
        <div className="title">
          <h3>{r.display_name}</h3>
          <p className="muted">
            {r.material_group_label} · {r.standard}
          </p>
        </div>
        {r.rank === 1 && <span className="badge best">Best overall</span>}
      </div>

      <div className="metric">
        <span>Suitability</span>
        <div className="bar big">
          <div style={{ width: `${r.suitability_pct}%` }} />
        </div>
        <strong>{r.suitability_pct.toFixed(0)}%</strong>
      </div>
      <div className="metric small">
        <span>TOPSIS score</span>
        <strong>{r.topsis_score.toFixed(3)}</strong>
      </div>

      <div className="cost">
        <div>
          <span className="muted small">Estimated material cost</span>
          <div className={`cost-value ${r.price.available ? "" : "na"}`}>{r.cost.text}</div>
          <div className="small">{r.cost.vs_top}</div>
        </div>
        <span className={`badge basis ${r.price.basis}`}>{BASIS[r.price.basis] || r.price.basis}</span>
      </div>

      <div className="row wrap">
        {!editing ? (
          <button className="link" onClick={() => setEditing(true)}>
            {r.price.custom ? "Change your price" : "Enter your price"}
          </button>
        ) : (
          <div className="price-edit">
            <span>Rs/kg for {r.material_group_label}:</span>
            <input type="number" min="0" value={price} onChange={(e) => setPrice(e.target.value)} autoFocus />
            <button className="primary small" onClick={applyPrice}>
              Apply
            </button>
            {r.price.custom && (
              <button className="ghost small" onClick={() => { onOverride(r.material_group, null); setEditing(false); }}>
                Reset
              </button>
            )}
          </div>
        )}
        <button className="link" onClick={() => setOpen(!open)}>
          {open ? "Hide details" : "Why this material?"}
        </button>
      </div>

      {open && (
        <div className="why">
          <h4>Model suitability per target class</h4>
          {Object.entries(r.class_suitability_pct).map(([c, p]) => (
            <div className="wbar" key={c}>
              <span>{c}</span>
              <div className="bar">
                <div style={{ width: `${p}%` }} />
              </div>
              <span>{p.toFixed(0)}%</span>
            </div>
          ))}

          <h4>Price</h4>
          <p>
            <strong>{r.price.text}</strong> — {r.price.why}
          </p>
          <p className="muted small">
            Source: {r.price.url ? <a href={r.price.url} target="_blank" rel="noreferrer">{r.price.source}</a> : r.price.source}
            {" · "}retrieved {r.price.date}
          </p>

          <h4>Properties (from the department dataset)</h4>
          <table>
            <tbody>
              {PROPS.map(([k, label, unit]) => (
                <tr key={k}>
                  <td>{label}</td>
                  <td>
                    {r.properties[k] ?? "—"} {unit}
                    {k === "A5" && r.a5_imputed && <em className="muted"> (filled with family median)</em>}
                  </td>
                </tr>
              ))}
              <tr>
                <td>Corrosion score</td>
                <td>{r.corrosion_score}/5</td>
              </tr>
              <tr>
                <td>Dataset label</td>
                <td>{r.labelled_classes}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </article>
  );
}

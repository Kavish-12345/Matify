import ResultCard from "./ResultCard.jsx";
import { groupLabel } from "../labels.js";

export default function Results({ result, options, form, busy, priceOverrides, onOverride, onEdit, onNew }) {
  const w = result.weights_normalised || {};
  const overrides = Object.entries(priceOverrides);

  return (
    <div className="results">
      <div className="results-head">
        <div>
          <h2>Recommended materials{form.part_name ? ` for: ${form.part_name}` : ""}</h2>
          <p className="muted">
            {result.n_alloys_ranked} alloys ranked from {result.n_candidates} candidate rows · cost shown{" "}
            {result.cost_basis}
          </p>
        </div>
        <div className="row">
          <button className="ghost" onClick={onEdit}>
            Edit requirements
          </button>
          <button className="ghost" onClick={onNew}>
            New search
          </button>
        </div>
      </div>

      <div className="explain-strip">
        <div>
          <strong>Target classes</strong>
          <div className="chips">
            {Object.entries(result.targets).map(([c, imp]) => (
              <span key={c} className="chip static">
                {c} <em>×{imp}</em>
              </span>
            ))}
          </div>
        </div>
        <div>
          <strong>TOPSIS weights</strong>
          <div className="weights">
            {Object.entries(w).map(([k, v]) => (
              <div key={k} className="wbar">
                <span>{k}</span>
                <div className="bar">
                  <div style={{ width: `${v * 100}%` }} />
                </div>
                <span>{Math.round(v * 100)}%</span>
              </div>
            ))}
          </div>
        </div>
        {overrides.length > 0 && (
          <div>
            <strong>Your prices</strong>
            <div className="chips">
              {overrides.map(([g, v]) => (
                <span key={g} className="chip custom">
                  {groupLabel(options, g)}: Rs {v}/kg{" "}
                  <button className="x" onClick={() => onOverride(g, null)} title="Remove">
                    ×
                  </button>
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {result.message && <div className="error">{result.message}</div>}
      {busy && <div className="muted">Re-ranking…</div>}

      <div className="cards">
        {result.results.map((r) => (
          <ResultCard key={r.material} r={r} onOverride={onOverride} />
        ))}
      </div>

      <p className="muted small">{result.note}</p>
    </div>
  );
}

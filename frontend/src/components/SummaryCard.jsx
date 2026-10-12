import { FIELD_LABELS, FIELD_ORDER, REQUIRED } from "../api.js";
import { formatValue } from "../labels.js";

// variant: "panel" (form mode side panel) | "inline" (card inside the chat) | "list" (dropdown, no buttons)
export default function SummaryCard({ variant = "panel", options, form, complete, busy, onConfirm, onEdit }) {
  const done = FIELD_ORDER.filter((k) => form[k] !== null && form[k] !== undefined).length;
  const rows = variant === "inline" ? FIELD_ORDER.filter((k) => form[k] !== null && form[k] !== undefined) : FIELD_ORDER;

  return (
    <div className={`summary ${variant}`}>
      {variant === "inline" && (
        <div className="tb-head">
          <span>REQUIREMENT SPECIFICATION</span>
          <span>DWG MAT-{String(Math.abs([...(form.part_name || "part")].reduce((a, c) => (a * 31 + c.charCodeAt(0)) | 0, 7)) % 10000).padStart(4, "0")}</span>
          <span>{new Date().toLocaleDateString()}</span>
        </div>
      )}
      {variant !== "list" && (
        <div className="summary-head">
          <h2>{variant === "inline" ? `Part: ${form.part_name || "—"}` : "Requirement summary"}</h2>
          <span className="muted small">
            {done}/{FIELD_ORDER.length}
          </span>
        </div>
      )}
      {variant === "panel" && (
        <div className="progress">
          <div style={{ width: `${(done / FIELD_ORDER.length) * 100}%` }} />
        </div>
      )}

      <ul className="summary-list">
        {rows.map((k) => {
          const v = formatValue(options, k, form[k]);
          const words = form.user_words?.[k];
          return (
            <li key={k} className={v ? "filled" : ""}>
              <span className="k">
                {FIELD_LABELS[k]}
                {!REQUIRED.includes(k) && variant === "panel" && <em> (optional)</em>}
              </span>
              <span className="v">{v || <span className="muted">—</span>}</span>
              {words && variant !== "inline" && <span className="words">“{words}”</span>}
            </li>
          );
        })}
      </ul>

      {variant !== "list" &&
        (complete ? (
          <>
            <p className="muted small">Results are computed only after you confirm.</p>
            <div className="row">
              <button className="primary" onClick={onConfirm} disabled={busy}>
                {busy ? "Ranking…" : "Confirm & find materials"}
              </button>
              <button className="ghost" onClick={onEdit}>
                Edit in form
              </button>
            </div>
          </>
        ) : (
          <p className="muted small">Answer all fields (or choose “Not sure”) to continue.</p>
        ))}
    </div>
  );
}

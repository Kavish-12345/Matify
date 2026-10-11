import { groupLabel } from "../labels.js";

// Plain form that fills exactly the same fields as the chat and calls the same /api/recommend.
export default function NoAIForm({ options, form, setForm, onReview }) {
  const set = (k, v) => setForm({ ...form, [k]: v });
  const groups = [...options.families, ...Object.keys(options.material_groups)];

  // properties = the classes the trained model predicts (from /api/options)
  function toggleProperty(v) {
    let cur = form.properties || [];
    if (v === "not_sure") cur = cur.includes("not_sure") ? [] : ["not_sure"];
    else cur = cur.includes(v) ? cur.filter((x) => x !== v) : [...cur.filter((x) => x !== "not_sure"), v];
    const real = cur.filter((x) => x !== "not_sure");
    let primary = form.primary_property;
    if (cur.includes("not_sure")) primary = "not_sure";
    else if (real.length === 1) primary = real[0];
    else if (!real.includes(primary)) primary = null;
    setForm({ ...form, properties: cur.length ? cur : null, primary_property: cur.length ? primary : null });
  }
  const chosen = (form.properties || []).filter((x) => x !== "not_sure");

  function setLimit(k, v) {
    const lim = { ...(form.min_limits || {}) };
    if (v === "") delete lim[k];
    else lim[k] = Number(v);
    set("min_limits", lim);
  }

  function toggleGroup(field, g) {
    const cur = form[field] || [];
    set(field, cur.includes(g) ? cur.filter((x) => x !== g) : [...cur, g]);
  }

  // Optional fields left blank count as "none" so the summary can be confirmed.
  function review() {
    setForm({
      ...form,
      volume_cm3: form.volume_cm3 ?? "not_sure",
      min_limits: form.min_limits ?? {},
      include: form.include ?? [],
      avoid: form.avoid ?? [],
    });
    onReview();
  }

  const select = (field, label) => (
    <label className="field">
      <span>{label}</span>
      <select value={form[field] || ""} onChange={(e) => set(field, e.target.value || null)}>
        <option value="">Choose…</option>
        {options.fields[field].map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );

  return (
    <div className="noai">
      <h2>Requirements form</h2>
      <p className="muted">Same questions as the chat. Choose “Not sure” whenever you don't know.</p>

      <label className="field">
        <span>Part name</span>
        <input value={form.part_name || ""} onChange={(e) => set("part_name", e.target.value || null)} placeholder="e.g. Gear shaft" />
      </label>

      <div className="field">
        <span>Which properties does the part need? (choose one or more)</span>
        <div className="prop-list">
          {options.fields.properties.map((o) => {
            const on = form.properties?.includes(o.value);
            return (
              <button type="button" key={o.value} className={`prop ${on ? "on" : ""}`} onClick={() => toggleProperty(o.value)}>
                <span className={`qbox ${on ? "on" : ""}`}>{on ? "✓" : ""}</span>
                <span className="qlabel">
                  {o.label}
                  <span className="qdesc">
                    {o.description}
                    {o.examples ? ` · e.g. ${o.examples}` : ""}
                  </span>
                </span>
              </button>
            );
          })}
          <button
            type="button"
            className={`chip ${form.properties?.includes("not_sure") ? "on" : ""}`}
            style={{ alignSelf: "flex-start" }}
            onClick={() => toggleProperty("not_sure")}
          >
            Not sure
          </button>
        </div>
      </div>

      {chosen.length > 1 && (
        <label className="field">
          <span>Which one matters most?</span>
          <select value={form.primary_property || ""} onChange={(e) => set("primary_property", e.target.value || null)}>
            <option value="">Choose…</option>
            {chosen.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
      )}

      <div className="grid2">
        {select("environment", "Environment")}
        {select("weight_priority", "How important is low weight?")}
        {select("cost_priority", "How important is low cost?")}
        <label className="field">
          <span>Part volume (cm³, optional)</span>
          <input
            type="number"
            min="0"
            value={typeof form.volume_cm3 === "number" ? form.volume_cm3 : ""}
            onChange={(e) => set("volume_cm3", e.target.value ? Number(e.target.value) : null)}
            placeholder="for cost per part"
          />
        </label>
      </div>

      <details className="optional">
        <summary>Optional: minimum limits and material groups</summary>
        <div className="grid2">
          {Object.entries(options.min_limits).map(([k, label]) => (
            <label className="field" key={k}>
              <span>{label}</span>
              <input type="number" min="0" value={form.min_limits?.[k] ?? ""} onChange={(e) => setLimit(k, e.target.value)} />
            </label>
          ))}
        </div>
        {["include", "avoid"].map((field) => (
          <div className="field" key={field}>
            <span>{field === "include" ? "Only consider" : "Avoid"}</span>
            <div className="chips">
              {groups.map((g) => (
                <button
                  type="button"
                  key={g}
                  className={`chip small ${form[field]?.includes(g) ? (field === "avoid" ? "off" : "on") : ""}`}
                  onClick={() => toggleGroup(field, g)}
                >
                  {groupLabel(options, g)}
                </button>
              ))}
            </div>
          </div>
        ))}
      </details>

      <button className="primary" onClick={review}>
        Review summary
      </button>
    </div>
  );
}

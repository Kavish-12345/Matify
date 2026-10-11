import { useEffect, useState } from "react";

// Question popup docked above the input box. Answers are sent as structured values
// (recorded directly by code) and also shown as the user's message in the chat.
export default function QuestionCard({ spec, onAnswer, onClose }) {
  const [picked, setPicked] = useState(spec.preselected || []);
  const [num, setNum] = useState("");
  const [limits, setLimits] = useState({});
  const [active, setActive] = useState(0);

  useEffect(() => {
    setPicked(spec.preselected || []);
    setNum("");
    setLimits({});
    setActive(0);
  }, [spec.field]);

  const opts = spec.options || [];
  const enabled = opts.filter((o) => !o.disabled);

  function notSure() {
    onAnswer("not_sure", "Not sure");
  }
  function skip() {
    onAnswer("none", "Skip");
  }
  function chooseSingle(o) {
    onAnswer(o.value, o.label);
  }
  function toggle(o) {
    if (o.disabled) return;
    setPicked((p) => (p.includes(o.value) ? p.filter((v) => v !== o.value) : [...p, o.value]));
  }
  function submitMulti() {
    if (!picked.length) return;
    const labels = opts.filter((o) => picked.includes(o.value)).map((o) => o.label);
    onAnswer(picked.join(", "), labels.join(", "));
  }
  function submitNumber() {
    const v = Number(num);
    if (!(v > 0)) return;
    onAnswer(String(v), `${v} ${spec.unit || ""}`.trim());
  }
  function submitLimits() {
    const entries = Object.entries(limits).filter(([, v]) => v !== "" && Number(v) > 0);
    if (!entries.length) return skip();
    const value = entries.map(([k, v]) => `${k}=${Number(v)}`).join(", ");
    const text = entries
      .map(([k, v]) => {
        const o = opts.find((x) => x.value === k);
        return `${o ? o.label.replace(/\s*\(.*\)/, "") : k} ${Number(v)} ${o?.unit || ""}`.trim();
      })
      .join(", ");
    onAnswer(value, text);
  }

  const canContinue =
    spec.type === "multi" ? picked.length > 0 : spec.type === "number" ? Number(num) > 0 : spec.type === "limits";

  function submit() {
    if (spec.type === "multi") submitMulti();
    else if (spec.type === "number") submitNumber();
    else if (spec.type === "limits") submitLimits();
  }

  // keyboard: 1-9 pick, arrows move, Enter confirm, Esc close
  useEffect(() => {
    function onKey(e) {
      const tag = document.activeElement?.tagName;
      const typing = tag === "TEXTAREA" || tag === "INPUT";
      if (e.key === "Escape") return onClose();
      if (typing) {
        if (e.key === "Enter" && tag === "INPUT" && canContinue) {
          e.preventDefault();
          submit();
        }
        return;
      }
      if (/^[1-9]$/.test(e.key) && (spec.type === "single" || spec.type === "multi")) {
        const o = opts[Number(e.key) - 1];
        if (o) spec.type === "single" ? chooseSingle(o) : toggle(o);
      } else if (e.key === "ArrowDown") {
        setActive((a) => Math.min(a + 1, opts.length - 1));
      } else if (e.key === "ArrowUp") {
        setActive((a) => Math.max(a - 1, 0));
      } else if (e.key === "Enter") {
        const o = opts[active];
        if (spec.type === "single" && o) chooseSingle(o);
        else if (canContinue) submit();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  return (
    <div className="qcard" role="dialog" aria-label={spec.title}>
      <div className="qhead">
        <div>
          <div className="qtitle">{spec.title}</div>
          <div className="qsub">
            {spec.subtitle ||
              (spec.type === "multi" ? "Choose one or more" : spec.type === "single" ? "Choose one" : spec.optional ? "Optional" : "")}
          </div>
        </div>
        <div className="qmeta">
          <span>
            {spec.step} of {spec.total}
          </span>
          <button className="qclose" onClick={onClose} aria-label="Close" title="Close (Esc) and type instead">
            ✕
          </button>
        </div>
      </div>

      {(spec.type === "single" || spec.type === "multi") && (
        <div className="qopts">
          {opts.map((o, i) => {
            const on = picked.includes(o.value);
            return (
              <button
                key={o.value}
                className={`qopt ${i === active ? "active" : ""} ${on ? "on" : ""} ${o.disabled ? "disabled" : ""}`}
                onMouseEnter={() => setActive(i)}
                onClick={() => (spec.type === "single" ? chooseSingle(o) : toggle(o))}
                disabled={o.disabled}
                title={o.disabled ? "Already chosen in the other list" : ""}
              >
                {spec.type === "multi" ? <span className={`qbox ${on ? "on" : ""}`}>{on ? "✓" : ""}</span> : <span className="qnum">{i + 1}</span>}
                <span className="qlabel">
                  {o.label}
                  {o.description && (
                    <span className="qdesc">
                      {o.description}
                      {o.examples ? ` · e.g. ${o.examples}` : ""}
                    </span>
                  )}
                </span>
                {spec.preselected?.includes(o.value) && <span className="qtag sugg">suggested</span>}
                {o.disabled && <span className="qtag">in other list</span>}
              </button>
            );
          })}
        </div>
      )}

      {spec.type === "number" && (
        <div className="qinputs">
          <label className="qfield">
            <span>Volume</span>
            <div className="qinput">
              <input type="number" min="0" value={num} onChange={(e) => setNum(e.target.value)} placeholder="e.g. 120" autoFocus />
              <em>{spec.unit}</em>
            </div>
            <small>{spec.hint}</small>
          </label>
        </div>
      )}

      {spec.type === "limits" && (
        <div className="qinputs grid">
          {opts.map((o, i) => (
            <label className="qfield" key={o.value}>
              <span>{o.label.replace(/\s*\(.*\)/, "")}</span>
              <div className="qinput">
                <input
                  type="number"
                  min="0"
                  value={limits[o.value] ?? ""}
                  onChange={(e) => setLimits({ ...limits, [o.value]: e.target.value })}
                  placeholder={o.hint}
                  autoFocus={i === 0}
                />
                <em>{o.unit}</em>
              </div>
            </label>
          ))}
        </div>
      )}

      <div className="qfoot">
        <div className="row">
          <button className="qbtn" onClick={notSure}>
            Not sure
          </button>
          {spec.optional && (
            <button className="qbtn" onClick={skip}>
              Skip
            </button>
          )}
        </div>
        {spec.type !== "single" && (
          <button className="qcontinue" onClick={submit} disabled={!canContinue}>
            Continue →
          </button>
        )}
      </div>
    </div>
  );
}

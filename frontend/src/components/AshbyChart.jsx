import { useMemo, useState } from "react";

// Ashby-style property chart (log-log): tensile strength vs density for every material
// in the dataset, coloured by family. Optional `highlight` = material names to mark.
export const FAMILY_COLORS = {
  ferrous: "#60a5fa",
  aluminium: "#22d3ee",
  copper: "#f59e0b",
  magnesium: "#c084fc",
};
const FAMILY_NAMES = { ferrous: "Steels & cast irons", aluminium: "Aluminium alloys", copper: "Copper alloys", magnesium: "Magnesium alloys" };

const X_MIN = 1500, X_MAX = 10000, Y_MIN = 50, Y_MAX = 3000;
const W = 760, H = 440, PAD = { l: 64, r: 20, t: 18, b: 48 };
const lx = (v) => PAD.l + ((Math.log10(v) - Math.log10(X_MIN)) / (Math.log10(X_MAX) - Math.log10(X_MIN))) * (W - PAD.l - PAD.r);
const ly = (v) => H - PAD.b - ((Math.log10(v) - Math.log10(Y_MIN)) / (Math.log10(Y_MAX) - Math.log10(Y_MIN))) * (H - PAD.t - PAD.b);

const X_TICKS = [1500, 2000, 3000, 5000, 7000, 10000];
const Y_TICKS = [50, 100, 200, 500, 1000, 2000, 3000];

export default function AshbyChart({ materials = [], highlight = [], compact = false }) {
  const [hover, setHover] = useState(null);
  const [hidden, setHidden] = useState([]);
  const hl = useMemo(() => new Set(highlight), [highlight]);

  const pts = useMemo(
    () => materials.filter((m) => m.Su > 0 && m.Ro > 0 && m.Ro >= X_MIN && m.Ro <= X_MAX),
    [materials]
  );
  const shown = pts.filter((m) => !hidden.includes(m.family) && !hl.has(m.Material));
  const marked = pts.filter((m) => hl.has(m.Material));
  // one label per highlighted material name
  const labelled = [];
  const seen = new Set();
  marked.forEach((m) => {
    if (!seen.has(m.Material)) {
      seen.add(m.Material);
      labelled.push(m);
    }
  });

  const toggle = (f) => setHidden((h) => (h.includes(f) ? h.filter((x) => x !== f) : [...h, f]));

  return (
    <div className={`ashby ${compact ? "compact" : ""}`}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Tensile strength versus density for all materials">
        {/* grid */}
        {X_TICKS.map((t) => (
          <g key={`x${t}`}>
            <line x1={lx(t)} x2={lx(t)} y1={PAD.t} y2={H - PAD.b} className="ash-grid" />
            <text x={lx(t)} y={H - PAD.b + 18} textAnchor="middle" className="ash-tick">{t.toLocaleString()}</text>
          </g>
        ))}
        {Y_TICKS.map((t) => (
          <g key={`y${t}`}>
            <line x1={PAD.l} x2={W - PAD.r} y1={ly(t)} y2={ly(t)} className="ash-grid" />
            <text x={PAD.l - 8} y={ly(t) + 4} textAnchor="end" className="ash-tick">{t}</text>
          </g>
        ))}
        <text x={(W + PAD.l) / 2} y={H - 8} textAnchor="middle" className="ash-axis">DENSITY ρ (kg/m³) · log scale</text>
        <text x={16} y={(H - PAD.b + PAD.t) / 2} textAnchor="middle" className="ash-axis" transform={`rotate(-90 16 ${(H - PAD.b + PAD.t) / 2})`}>
          TENSILE STRENGTH Su (MPa) · log
        </text>
        {/* specific-strength guide line (Su/ρ constant) */}
        <line x1={lx(1500)} y1={ly(150)} x2={lx(10000)} y2={ly(1000)} className="ash-guide" />
        <text x={lx(1560)} y={ly(160) - 8} className="ash-guide-text">Su/ρ = const (equal specific strength)</text>

        {shown.map((m, i) => (
          <circle
            key={i}
            cx={lx(m.Ro)}
            cy={ly(m.Su)}
            r={compact ? 2.6 : 3.2}
            fill={FAMILY_COLORS[m.family] || "#888"}
            className={`ash-pt ${marked.length ? "dim" : ""}`}
            onMouseEnter={() => setHover(m)}
            onMouseLeave={() => setHover(null)}
          />
        ))}
        {marked.map((m, i) => (
          <circle key={`h${i}`} cx={lx(m.Ro)} cy={ly(m.Su)} r={6} className="ash-hl" onMouseEnter={() => setHover(m)} onMouseLeave={() => setHover(null)} />
        ))}
        {labelled.slice(0, 5).map((m, i) => (
          <text key={`l${i}`} x={lx(m.Ro) + 9} y={ly(m.Su) - 8 - i * 2} className="ash-hl-label">#{highlight.indexOf(m.Material) + 1} {m.Material.slice(0, 22)}</text>
        ))}

        {hover && (
          <g transform={`translate(${Math.min(lx(hover.Ro) + 10, W - 230)} ${Math.max(ly(hover.Su) - 60, 10)})`} className="ash-tip">
            <rect width="220" height="52" rx="6" />
            <text x="10" y="20" className="t1">{hover.Material.slice(0, 30)}</text>
            <text x="10" y="38" className="t2">Su {hover.Su} MPa · ρ {hover.Ro} kg/m³</text>
          </g>
        )}
      </svg>
      <div className="ash-legend">
        {Object.entries(FAMILY_COLORS).map(([f, c]) => (
          <button key={f} className={hidden.includes(f) ? "off" : ""} onClick={() => toggle(f)}>
            <span style={{ background: c }} /> {FAMILY_NAMES[f]}
          </button>
        ))}
        {highlight.length > 0 && (
          <span className="ash-legend-hl">
            <span /> Your shortlist
          </span>
        )}
      </div>
    </div>
  );
}

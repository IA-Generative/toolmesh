import { useId, useRef, useState } from "react";

// Pièces de visualisation du tableau de bord. Les couleurs sont des rôles (variables CSS de `.viz-root`, voir
// SearchQuality.css) : les teintes catégorielles ont été validées en clair et en sombre avec le validateur de palette.

const W = 640;
const H = 220;
const M = { top: 12, right: 16, bottom: 28, left: 36 };

const compact = (n) => (n >= 1000 ? `${Math.round(n / 100) / 10}k` : String(n));
const niceMax = (max) => {
  if (max <= 4) return 4;
  const step = 10 ** Math.floor(Math.log10(max));
  return Math.ceil(max / step) * step;
};
const dayLabel = (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString("fr-FR", { day: "numeric", month: "short" });

// Courbes sur un même axe (jamais deux échelles) : une ligne de 2 px par série, repère de 8 px au dernier point,
// repère vertical qui suit le pointeur (ou les flèches du clavier) et infobulle listant toutes les séries.
export function LineChart({ title, days, series }) {
  const [hover, setHover] = useState(null);
  const [asTable, setAsTable] = useState(false);
  const ref = useRef(null);
  const id = useId();

  const max = niceMax(Math.max(1, ...days.flatMap((d) => series.map((s) => d[s.key]))));
  const x = (i) => M.left + (days.length < 2 ? 0 : (i * (W - M.left - M.right)) / (days.length - 1));
  const y = (v) => M.top + (1 - v / max) * (H - M.top - M.bottom);
  const ticks = [0, max / 2, max];
  const last = days.length - 1;

  const nearest = (clientX) => {
    const box = ref.current.getBoundingClientRect();
    const px = ((clientX - box.left) / box.width) * W;
    return Math.max(0, Math.min(last, Math.round(((px - M.left) / (W - M.left - M.right)) * last)));
  };
  const onKey = (e) => {
    if (e.key === "ArrowLeft") setHover((h) => Math.max(0, (h ?? last) - 1));
    else if (e.key === "ArrowRight") setHover((h) => Math.min(last, (h ?? last - 1) + 1));
    else if (e.key === "Escape") setHover(null);
    else return;
    e.preventDefault();
  };

  return (
    <figure className="viz-figure">
      <figcaption className="viz-figure__head">
        <span className="viz-figure__title" id={`${id}-t`}>{title}</span>
        <ul className="viz-legend">
          {series.map((s) => (
            <li key={s.key}>
              <span className="viz-legend__key" style={{ background: `var(${s.color})` }} aria-hidden="true" />
              {s.label}
            </li>
          ))}
        </ul>
        <button type="button" className="fr-btn fr-btn--tertiary-no-outline fr-btn--sm" onClick={() => setAsTable((v) => !v)}>
          {asTable ? "Voir le graphique" : "Voir le tableau"}
        </button>
      </figcaption>

      {asTable ? (
        <div className="viz-table">
          <table>
            <caption className="fr-sr-only">{title}</caption>
            <thead>
              <tr><th scope="col">Jour</th>{series.map((s) => <th key={s.key} scope="col">{s.label}</th>)}</tr>
            </thead>
            <tbody>
              {days.map((d) => (
                <tr key={d.date}><th scope="row">{dayLabel(d.date)}</th>{series.map((s) => <td key={s.key}>{d[s.key]}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="viz-plot">
          <svg
            ref={ref}
            viewBox={`0 0 ${W} ${H}`}
            role="img"
            aria-labelledby={`${id}-t`}
            tabIndex={0}
            onPointerMove={(e) => setHover(nearest(e.clientX))}
            onPointerLeave={() => setHover(null)}
            onKeyDown={onKey}
            onBlur={() => setHover(null)}
          >
            {ticks.map((t) => (
              <g key={t}>
                <line x1={M.left} x2={W - M.right} y1={y(t)} y2={y(t)} className="viz-grid" />
                <text x={M.left - 6} y={y(t) + 4} textAnchor="end" className="viz-axis">{compact(t)}</text>
              </g>
            ))}
            {[0, Math.floor(last / 2), last].filter((v, i, a) => a.indexOf(v) === i && days[v]).map((i) => (
              <text key={i} x={x(i)} y={H - 8} textAnchor={i === 0 ? "start" : i === last ? "end" : "middle"} className="viz-axis">
                {dayLabel(days[i].date)}
              </text>
            ))}
            {series.map((s) => (
              <g key={s.key} style={{ color: `var(${s.color})` }}>
                <polyline
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinejoin="round"
                  strokeLinecap="round"
                  points={days.map((d, i) => `${x(i)},${y(d[s.key])}`).join(" ")}
                />
                {days.length > 0 && (
                  <circle cx={x(last)} cy={y(days[last][s.key])} r="4" fill="currentColor" className="viz-ring" />
                )}
              </g>
            ))}
            {hover !== null && days[hover] && (
              <g>
                <line x1={x(hover)} x2={x(hover)} y1={M.top} y2={H - M.bottom} className="viz-cursor" />
                {series.map((s) => (
                  <circle key={s.key} cx={x(hover)} cy={y(days[hover][s.key])} r="4" fill={`var(${s.color})`} className="viz-ring" />
                ))}
              </g>
            )}
          </svg>
          {hover !== null && days[hover] && (
            <div className="viz-tooltip" role="status" style={{ left: `${(x(hover) / W) * 100}%` }}>
              <div className="viz-tooltip__title">{dayLabel(days[hover].date)}</div>
              {series.map((s) => (
                <div key={s.key} className="viz-tooltip__row">
                  <span className="viz-legend__key viz-legend__key--line" style={{ background: `var(${s.color})` }} aria-hidden="true" />
                  <strong>{days[hover][s.key]}</strong>
                  <span>{s.label}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </figure>
  );
}

// Barres horizontales d'une seule teinte (la magnitude est séquentielle) : étiquette en texte, valeur au bout de la barre.
export function BarList({ title, rows, empty = "Rien à signaler sur la période." }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <figure className="viz-figure">
      <figcaption className="viz-figure__head"><span className="viz-figure__title">{title}</span></figcaption>
      {rows.length === 0 ? (
        <p className="fr-text--sm viz-muted">{empty}</p>
      ) : (
        <ul className="viz-bars">
          {rows.map((r) => (
            <li key={r.label} className="viz-bars__row" title={`${r.label} : ${r.value}`}>
              <span className="viz-bars__label">{r.label}</span>
              <span className="viz-bars__track">
                <span className="viz-bars__bar" style={{ width: `${Math.max(2, (r.value / max) * 100)}%` }} />
              </span>
              <span className="viz-bars__value">{r.value}</span>
            </li>
          ))}
        </ul>
      )}
    </figure>
  );
}

// Un chiffre et ce qu'il mesure ; `hint` donne le contexte (période, taux).
export function Stat({ label, value, hint }) {
  return (
    <div className="viz-stat">
      <span className="viz-stat__label">{label}</span>
      <span className="viz-stat__value">{value}</span>
      {hint && <span className="viz-stat__hint">{hint}</span>}
    </div>
  );
}

// Un rapport à 100 % : la piste est une teinte plus claire de la même rampe que le remplissage.
export function Meter({ label, ratio, hint }) {
  const pct = Math.round(ratio * 100);
  return (
    <div className="viz-stat">
      <span className="viz-stat__label">{label}</span>
      <span className="viz-stat__value">{pct} %</span>
      <span className="viz-meter" role="meter" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label={label}>
        <span className="viz-meter__fill" style={{ width: `${pct}%` }} />
      </span>
      {hint && <span className="viz-stat__hint">{hint}</span>}
    </div>
  );
}

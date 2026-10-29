import React from "react";

export interface ChartDatum {
  label: string;
  value: number;
  /** CSS colour; defaults cycle through the theme accents. */
  color?: string;
}

const PALETTE = ["var(--tblr-primary)", "#2dd4bf", "#f59e0b", "#a855f7", "#ef4444", "#0ea5e9", "#22c55e"];

/**
 * Donut chart drawn with SVG strokes. The legend lists every value as text,
 * so the numbers never depend on colour or on seeing the chart.
 */
export const DonutChart: React.FC<{ data: ChartDatum[]; centerLabel: string; ariaLabel: string }> = ({ data, centerLabel, ariaLabel }) => {
  const total = data.reduce((sum, d) => sum + d.value, 0);
  const r = 42;
  const circumference = 2 * Math.PI * r;
  let offset = 0;
  return (
    <div className="ssi-donut">
      <svg viewBox="0 0 120 120" role="img" aria-label={`${ariaLabel}: ${data.map((d) => `${d.label} ${d.value}`).join(", ")}`}>
        <circle cx="60" cy="60" r={r} className="ssi-donut-track" />
        {total > 0 && data.map((d, i) => {
          const length = (d.value / total) * circumference;
          const segment = (
            <circle
              key={d.label}
              cx="60"
              cy="60"
              r={r}
              className="ssi-donut-seg"
              stroke={d.color ?? PALETTE[i % PALETTE.length]}
              strokeDasharray={`${Math.max(length - 2, 0)} ${circumference}`}
              strokeDashoffset={-offset}
              style={{ "--i": i } as React.CSSProperties}
            />
          );
          offset += length;
          return segment;
        })}
        <text x="60" y="57" textAnchor="middle" className="ssi-donut-total">{total}</text>
        <text x="60" y="73" textAnchor="middle" className="ssi-donut-caption">{centerLabel}</text>
      </svg>
      <ul className="ssi-legend">
        {data.map((d, i) => (
          <li key={d.label}>
            <span className="ssi-legend-dot" style={{ background: d.color ?? PALETTE[i % PALETTE.length] }} aria-hidden="true" />
            <span className="flex-fill">{d.label}</span>
            <strong>{d.value}</strong>
          </li>
        ))}
      </ul>
    </div>
  );
};

/** Vertical bar chart; each bar has a title tooltip and the series is described in text. */
export const BarChart: React.FC<{ data: ChartDatum[]; ariaLabel: string; height?: number }> = ({ data, ariaLabel, height = 160 }) => {
  const max = Math.max(1, ...data.map((d) => d.value));
  const w = 100 / Math.max(data.length, 1);
  return (
    <figure className="ssi-bars mb-0">
      <svg viewBox={`0 0 100 ${height / 4}`} preserveAspectRatio="none" role="img" aria-label={`${ariaLabel}: ${data.map((d) => `${d.label} ${d.value}`).join(", ")}`}>
        <defs>
          <linearGradient id="ssi-bar-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="var(--tblr-primary)" />
            <stop offset="1" stopColor="#2dd4bf" stopOpacity=".55" />
          </linearGradient>
        </defs>
        {data.map((d, i) => {
          const h = (d.value / max) * (height / 4 - 2);
          return (
            <rect
              key={d.label}
              className="ssi-bar"
              x={i * w + w * 0.18}
              y={height / 4 - h}
              width={w * 0.64}
              height={Math.max(h, d.value > 0 ? 0.6 : 0)}
              rx="0.8"
              fill="url(#ssi-bar-fill)"
              style={{ "--i": i } as React.CSSProperties}
            >
              <title>{`${d.label}: ${d.value}`}</title>
            </rect>
          );
        })}
      </svg>
      <figcaption className="ssi-bars-axis" aria-hidden="true">
        {data.map((d, i) => <span key={d.label} style={{ width: `${w}%` }}>{i % Math.ceil(data.length / 7) === 0 ? d.label : ""}</span>)}
      </figcaption>
    </figure>
  );
};

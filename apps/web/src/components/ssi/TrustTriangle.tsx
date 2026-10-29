import React from "react";

/**
 * The SSI trust triangle: the issuer signs, the holder keeps and presents,
 * the verifier checks the signature against the Trust Registry. Colours follow
 * the active theme through currentColor and the accent variable.
 */
export const TrustTriangle: React.FC = () => (
  <svg className="ssi-triangle" viewBox="0 0 520 400" role="img" aria-labelledby="triangle-title triangle-desc">
    <title id="triangle-title">SSI trust triangle</title>
    <desc id="triangle-desc">Issuer issues a credential to the holder; the holder presents it to the verifier; the verifier checks issuer trust in the Trust Registry.</desc>
    <defs>
      <linearGradient id="tt-edge" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="var(--tblr-primary)" />
        <stop offset="1" stopColor="#2dd4bf" />
      </linearGradient>
      <marker id="tt-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M0 0 10 5 0 10z" fill="url(#tt-edge)" />
      </marker>
    </defs>
    <g fill="none" stroke="url(#tt-edge)" strokeWidth="2.5" strokeLinecap="round">
      <path d="M232 92 110 290" markerEnd="url(#tt-arrow)" />
      <path d="M150 318h220" markerEnd="url(#tt-arrow)" />
      <path d="M410 290 288 92" strokeDasharray="6 8" opacity=".75" markerEnd="url(#tt-arrow)" />
    </g>
    <g fill="none" stroke="currentColor" strokeOpacity=".25" strokeDasharray="3 6">
      <path d="M260 210 260 92M260 210 110 318M260 210 410 318" />
    </g>
    <g className="ssi-triangle-labels" fill="currentColor" fontSize="13" fontWeight="600" textAnchor="middle">
      <text x="150" y="180" transform="rotate(-58 150 180)">issues credential</text>
      <text x="260" y="344">presents proof</text>
      <text x="370" y="180" transform="rotate(58 370 180)">trusts issuer</text>
    </g>
    {[
      { x: 260, y: 64, label: "Issuer", sub: "signs" },
      { x: 92, y: 318, label: "Holder", sub: "keeps & consents" },
      { x: 428, y: 318, label: "Verifier", sub: "checks" },
    ].map((node) => (
      <g key={node.label} transform={`translate(${node.x} ${node.y})`}>
        <circle r="36" className="ssi-triangle-node" />
        <circle r="36" fill="none" stroke="url(#tt-edge)" strokeWidth="2" />
        <text y="5" textAnchor="middle" fontSize="14" fontWeight="700" fill="currentColor">{node.label}</text>
        <text y="56" textAnchor="middle" fontSize="12" fill="currentColor" opacity=".65">{node.sub}</text>
      </g>
    ))}
    <g transform="translate(260 210)">
      <rect x="-62" y="-22" width="124" height="44" rx="12" className="ssi-triangle-node" />
      <rect x="-62" y="-22" width="124" height="44" rx="12" fill="none" stroke="currentColor" strokeOpacity=".35" />
      <text y="5" textAnchor="middle" fontSize="12.5" fontWeight="700" fill="currentColor">Trust Registry</text>
    </g>
  </svg>
);

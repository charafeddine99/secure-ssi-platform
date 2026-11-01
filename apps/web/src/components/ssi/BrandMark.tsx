import React from "react";
import { Link } from "react-router-dom";

/** Tabler `.navbar-brand` with the Secure SSI shield mark. */
export const BrandMark: React.FC<{ inverse?: boolean; to?: string; className?: string }> = ({ inverse = false, to = "/", className }) => (
  <Link to={to} className={["navbar-brand d-inline-flex align-items-center gap-2 text-decoration-none", className ?? ""].filter(Boolean).join(" ")} aria-label="Secure SSI Platform home">
    <svg width="32" height="32" viewBox="0 0 36 36" aria-hidden="true" focusable="false" className="flex-shrink-0">
      <rect width="36" height="36" rx="8" fill={inverse ? "#ffffff" : "#172b4d"} />
      <path d="M18 7l9 3.5v6.6c0 5.6-3.8 10-9 11.9-5.2-1.9-9-6.3-9-11.9v-6.6L18 7z" fill="none" stroke={inverse ? "#172b4d" : "#ffffff"} strokeWidth="2" />
      <path d="M14 18l3 3 5.5-6" fill="none" stroke={inverse ? "#066fd1" : "#7cb7ff"} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
    <span className="fw-bold">Secure SSI</span>
  </Link>
);

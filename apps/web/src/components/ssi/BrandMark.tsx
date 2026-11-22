import React from "react";
import { Link } from "react-router-dom";
import ssiLogo from "../../assets/ssi-logo.jpg";

/** Tabler `.navbar-brand` with the Secure SSI shield logo. */
export const BrandMark: React.FC<{ inverse?: boolean; to?: string; className?: string }> = ({ to = "/", className }) => (
  <Link to={to} className={["navbar-brand d-inline-flex align-items-center gap-2 text-decoration-none", className ?? ""].filter(Boolean).join(" ")} aria-label="Secure SSI Platform home">
    <span className="ssi-brand-logo-wrap flex-shrink-0" aria-hidden="true">
      <img src={ssiLogo} alt="" className="ssi-brand-logo" width={36} height={36} />
    </span>
    <span className="fw-bold">Secure SSI</span>
  </Link>
);

import React from "react";
import { Link } from "react-router-dom";
import ssiLogo from "../../assets/ssi-logo.png";

/** Tabler `.navbar-brand` with the Secure SSI shield logo. */
export const BrandMark: React.FC<{ inverse?: boolean; to?: string; className?: string }> = ({ to = "/", className }) => (
  <Link to={to} className={["navbar-brand d-inline-flex align-items-center gap-2 text-decoration-none", className ?? ""].filter(Boolean).join(" ")} aria-label="Secure SSI Platform home">
    <img src={ssiLogo} alt="" className="ssi-brand-logo flex-shrink-0" width={38} height={38} aria-hidden="true" />
    <span className="fw-bold">Secure SSI</span>
  </Link>
);

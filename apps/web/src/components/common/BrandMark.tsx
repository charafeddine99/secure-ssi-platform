import React from "react";

interface BrandMarkProps {
  className?: string;
  size?: number;
}

/** A compact identity-and-trust mark shared across the public and role workspaces. */
export const BrandMark: React.FC<BrandMarkProps> = ({ className, size = 36 }) => (
  <svg
    aria-hidden="true"
    className={className}
    width={size}
    height={size}
    viewBox="0 0 48 48"
    fill="none"
    focusable="false"
  >
    <path
      d="M24 4.5 39 10v12.1c0 9.9-6.2 16.4-15 21.4C15.2 38.5 9 32 9 22.1V10l15-5.5Z"
      stroke="currentColor"
      strokeWidth="2.2"
      strokeLinejoin="round"
    />
    <path
      d="M15.5 19h5l3.5 5 3.5-5h5M15.5 29h5l3.5-5 3.5 5h5"
      stroke="#78E1D1"
      strokeWidth="2.2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <circle cx="15.5" cy="19" r="2.2" fill="#DCEBFF" />
    <circle cx="32.5" cy="19" r="2.2" fill="#DCEBFF" />
    <circle cx="15.5" cy="29" r="2.2" fill="#DCEBFF" />
    <circle cx="32.5" cy="29" r="2.2" fill="#DCEBFF" />
    <circle cx="24" cy="24" r="2.6" fill="#78E1D1" />
  </svg>
);

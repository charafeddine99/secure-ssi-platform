import React from "react";
import { Link, type LinkProps } from "react-router-dom";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

interface SharedProps {
  variant?: ButtonVariant;
  size?: "md" | "sm";
  block?: boolean;
}

/** Tabler button conventions: plain `.btn` is the neutral surface button. */
const VARIANT_CLASS: Record<ButtonVariant, string> = {
  primary: "btn-primary",
  secondary: "",
  ghost: "btn-ghost-secondary",
  danger: "btn-danger",
};

function classes({ variant = "primary", size = "md", block = false }: SharedProps, extra?: string): string {
  return ["btn", VARIANT_CLASS[variant], size === "sm" ? "btn-sm" : "", block ? "w-100" : "", extra ?? ""].filter(Boolean).join(" ");
}

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, SharedProps {
  loading?: boolean;
  icon?: React.ReactNode;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant, size, block, loading = false, icon, className, children, disabled, type = "button", ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={classes({ variant, size, block }, className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? <span className="spinner-border spinner-border-sm me-2" aria-hidden="true" /> : icon && <span className="btn-icon-lead">{icon}</span>}
      {children}
    </button>
  );
});

export interface ButtonLinkProps extends LinkProps, SharedProps {
  icon?: React.ReactNode;
}

export const ButtonLink: React.FC<ButtonLinkProps> = ({ variant, size, block, icon, className, children, ...rest }) => (
  <Link className={classes({ variant, size, block }, className)} {...rest}>
    {icon && <span className="btn-icon-lead">{icon}</span>}
    {children}
  </Link>
);

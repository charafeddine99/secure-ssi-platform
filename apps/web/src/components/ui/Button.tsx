import React from "react";
import { Link, type LinkProps } from "react-router-dom";

export type ButtonVariant = "primary" | "secondary" | "quiet" | "danger";
export type ButtonSize = "default" | "small" | "large";

interface SharedButtonProps {
  variant?: ButtonVariant;
  size?: ButtonSize;
  className?: string;
  children: React.ReactNode;
}

type ButtonProps = SharedButtonProps & React.ButtonHTMLAttributes<HTMLButtonElement>;
type ButtonLinkProps = SharedButtonProps & Omit<LinkProps, "className" | "children">;

const buttonClasses = (
  variant: ButtonVariant,
  size: ButtonSize,
  className?: string
) => [
  "ui-button",
  `ui-button--${variant}`,
  size === "default" ? undefined : `ui-button--${size}`,
  className
].filter(Boolean).join(" ");

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "primary", size = "default", className, type = "button", children, ...props }, ref) => (
    <button
      {...props}
      ref={ref}
      type={type}
      className={buttonClasses(variant, size, className)}
      data-ui="button"
    >
      {children}
    </button>
  )
);

Button.displayName = "Button";

export const ButtonLink: React.FC<ButtonLinkProps> = ({
  variant = "primary",
  size = "default",
  className,
  children,
  ...props
}) => (
  <Link
    {...props}
    className={buttonClasses(variant, size, className)}
    data-ui="button"
  >
    {children}
  </Link>
);

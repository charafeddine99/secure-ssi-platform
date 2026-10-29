import React from "react";

interface CardProps extends Omit<React.HTMLAttributes<HTMLElement>, "title"> {
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
  footer?: React.ReactNode;
  as?: "section" | "article" | "div";
  muted?: boolean;
  headingLevel?: 2 | 3;
  /** Render children without `.card-body`, e.g. for a `.card-table`. */
  flush?: boolean;
  /** Tabler `.card-status-top` accent. */
  status?: "primary" | "success" | "warning" | "danger" | "info" | "secondary";
}

/** Tabler card: card-header (title, subtitle, card-actions), card-body, card-footer. */
export const Card: React.FC<CardProps> = ({
  title, subtitle, actions, footer, as = "section", muted = false, headingLevel = 2, flush = false, status, className, children, ...rest
}) => {
  const Tag = as;
  const Heading = headingLevel === 2 ? "h2" : "h3";
  const headingId = React.useId();
  return (
    <Tag
      className={["card", muted ? "bg-body-tertiary" : "", className ?? ""].filter(Boolean).join(" ")}
      aria-labelledby={title ? headingId : undefined}
      {...rest}
    >
      {status && <div className={`card-status-top bg-${status}`} />}
      {(title || actions) && (
        <div className="card-header">
          <div>
            {title && <Heading id={headingId} className="card-title">{title}</Heading>}
            {subtitle && <p className="card-subtitle mb-0 mt-1">{subtitle}</p>}
          </div>
          {actions && <div className="card-actions btn-list">{actions}</div>}
        </div>
      )}
      {flush ? children : children !== undefined && children !== null && children !== false && <div className="card-body">{children}</div>}
      {footer && <div className="card-footer">{footer}</div>}
    </Tag>
  );
};

/** Tabler "card-sm" stat tile: subheader label, h1-sized value, secondary hint. */
export const Stat: React.FC<{ label: string; value: React.ReactNode; hint?: React.ReactNode; icon?: React.ReactNode; tone?: string }> = ({
  label, value, hint, icon, tone = "primary",
}) => (
  <div className="card card-sm h-100">
    <div className="card-body">
      <div className="row align-items-center">
        {icon && (
          <div className="col-auto">
            <span className={`bg-${tone}-lt avatar`} aria-hidden="true">{icon}</span>
          </div>
        )}
        <div className="col">
          <div className="subheader">{label}</div>
          <div className="ssi-stat-value mt-1">{value}</div>
          {hint && <div className="text-secondary small mt-1">{hint}</div>}
        </div>
      </div>
    </div>
  </div>
);

/** Tabler `.datagrid` for label/value metadata. */
export const DataGrid: React.FC<{ items: Array<{ label: string; value: React.ReactNode } | false | null | undefined>; className?: string }> = ({ items, className }) => (
  <dl className={["datagrid mb-0", className ?? ""].filter(Boolean).join(" ")}>
    {items.filter(Boolean).map((item) => {
      const entry = item as { label: string; value: React.ReactNode };
      return (
        <div key={entry.label} className="datagrid-item">
          <dt className="datagrid-title">{entry.label}</dt>
          <dd className="datagrid-content mb-0">{entry.value}</dd>
        </div>
      );
    })}
  </dl>
);

/** Tabler responsive table; `data-label` cells stack below the chosen breakpoint (wide tables use md). */
export const Table: React.FC<{ caption: string; children: React.ReactNode; inCard?: boolean; className?: string; stackBelow?: "sm" | "md" }> = ({
  caption, children, inCard = true, className, stackBelow = "sm",
}) => (
  <div className="table-responsive">
    <table className={["table table-vcenter", `table-mobile-${stackBelow}`, inCard ? "card-table" : "", className ?? ""].filter(Boolean).join(" ")}>
      <caption className="visually-hidden">{caption}</caption>
      {children}
    </table>
  </div>
);

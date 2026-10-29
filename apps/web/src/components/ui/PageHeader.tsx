import React from "react";
import { Link } from "react-router-dom";

export interface Crumb {
  label: string;
  to?: string;
}

interface HeaderProps {
  title: string;
  eyebrow?: string;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  breadcrumbs?: Crumb[];
}

/** Tabler page header: breadcrumb, page-pretitle, page-title, actions column. */
export const PageHeader: React.FC<HeaderProps> = ({ title, eyebrow, description, actions, breadcrumbs }) => {
  React.useEffect(() => {
    document.title = `${title} · Secure SSI Platform`;
  }, [title]);
  return (
    <div className="page-header d-print-none">
      <div className="container-xl">
        <div className="row g-2 align-items-center">
          <div className="col">
            {breadcrumbs && breadcrumbs.length > 0 && (
              <nav aria-label="Breadcrumb">
                <ol className="breadcrumb breadcrumb-arrows mb-1">
                  {breadcrumbs.map((crumb, index) => (
                    <li key={`${crumb.label}-${index}`} className={["breadcrumb-item", crumb.to ? "" : "active"].filter(Boolean).join(" ")}>
                      {crumb.to ? <Link to={crumb.to}>{crumb.label}</Link> : <span aria-current="page">{crumb.label}</span>}
                    </li>
                  ))}
                </ol>
              </nav>
            )}
            {eyebrow && !breadcrumbs?.length && <div className="page-pretitle">{eyebrow}</div>}
            <h1 className="page-title">{title}</h1>
            {description && <p className="text-secondary mt-1 mb-0 page-description">{description}</p>}
          </div>
          {actions && (
            <div className="col-auto ms-auto d-print-none">
              <div className="btn-list">{actions}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

/**
 * Tabler page composition with the "navbar overlap" band: the page-header sits
 * on the brand artwork and the first row of page-body cards overlaps it.
 */
export const Page: React.FC<HeaderProps & { children: React.ReactNode; narrow?: boolean }> = ({ children, narrow = false, ...header }) => (
  <>
    <div className="ssi-band">
      <div className="ssi-band-art" aria-hidden="true" />
      <PageHeader {...header} />
    </div>
    <div className="page-body ssi-band-body">
      <div className={narrow ? "container-xl page-narrow" : "container-xl"}>
        <div className="vstack gap-3">{children}</div>
      </div>
    </div>
  </>
);

/** Tabler card grid (`row row-cards`); each child becomes one responsive column. */
export const Grid: React.FC<{ cols?: 2 | 3 | 4; deck?: boolean; children: React.ReactNode; className?: string }> = ({
  cols = 2, deck = true, children, className,
}) => {
  const col = cols === 4 ? "col-6 col-lg-3" : cols === 3 ? "col-md-6 col-lg-4" : "col-md-6";
  return (
    <div className={["row row-cards", deck ? "row-deck" : "", className ?? ""].filter(Boolean).join(" ")}>
      {React.Children.toArray(children).filter(Boolean).map((child, index) => (
        <div key={(React.isValidElement(child) && child.key) || index} className={cols === 4 ? col : `col-12 ${col}`}>{child}</div>
      ))}
    </div>
  );
};

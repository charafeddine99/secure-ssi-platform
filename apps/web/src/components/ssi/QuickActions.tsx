import React from "react";
import { Link } from "react-router-dom";
import { IconArrowUpRight } from "@tabler/icons-react";

export interface QuickAction {
  to: string;
  title: string;
  text: string;
  icon: React.ReactNode;
  /** Accent for the icon tile. */
  tone?: "indigo" | "teal" | "azure" | "orange" | "purple" | "green";
}

/** Large icon tiles linking to the role's real pages. */
export const QuickActions: React.FC<{ title?: string; actions: QuickAction[] }> = ({ title = "Quick actions", actions }) => (
  <section aria-label={title}>
    <h2 className="ssi-section-title">{title}</h2>
    <div className="row row-cards row-deck">
      {actions.map((action) => (
        <div key={action.to + action.title} className={actions.length >= 4 ? "col-6 col-lg-3" : "col-12 col-md-4"}>
          <Link to={action.to} className={`card ssi-action ssi-action-${action.tone ?? "indigo"} text-reset text-decoration-none`}>
            <div className="card-body">
              <div className="d-flex align-items-start justify-content-between mb-3">
                <span className="ssi-action-icon" aria-hidden="true">{action.icon}</span>
                <IconArrowUpRight size={18} className="ssi-action-arrow" aria-hidden="true" />
              </div>
              <div className="fw-semibold mb-1">{action.title}</div>
              <div className="text-secondary small">{action.text}</div>
            </div>
          </Link>
        </div>
      ))}
    </div>
  </section>
);

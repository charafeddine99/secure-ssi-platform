import React from "react";
import { IconArrowLeft } from "@tabler/icons-react";
import { ButtonLink } from "../../components/ui/Button.tsx";

/** Tabler error page (empty + empty-header). */
export const NotFoundPage: React.FC = () => {
  React.useEffect(() => { document.title = "Page not found · Secure SSI Platform"; }, []);
  return (
    <div className="page-body">
      <div className="container-tight py-4">
        <div className="empty">
          <div className="empty-header">404</div>
          <h1 className="empty-title">Page not found</h1>
          <p className="empty-subtitle text-secondary">The address does not match any page in this application.</p>
          <div className="empty-action">
            <ButtonLink to="/" icon={<IconArrowLeft size={18} aria-hidden="true" />}>Return home</ButtonLink>
          </div>
        </div>
      </div>
    </div>
  );
};

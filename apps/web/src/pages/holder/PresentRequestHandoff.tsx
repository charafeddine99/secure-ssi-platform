import React from "react";
import { Navigate, useSearchParams } from "react-router-dom";
import { Page } from "../../components/ui/PageHeader.tsx";
import { Alert } from "../../components/ui/Alert.tsx";
import { ButtonLink } from "../../components/ui/Button.tsx";

const REQUEST = /^session_[A-Za-z0-9_-]{16,80}$/;

/**
 * Where a phone lands after scanning a verifier's QR. Sign-in is enforced by the
 * route guard, which returns here. The value is only a handle: the consent page
 * loads the real request from the server, and nothing is shared until the
 * holder approves there.
 */
export const PresentRequestHandoff: React.FC = () => {
  const [params] = useSearchParams();
  const request = params.get("request") ?? "";
  if (REQUEST.test(request)) {
    return <Navigate to={`/wallet/consent?sessionId=${encodeURIComponent(request)}`} replace />;
  }
  return (
    <Page title="This request cannot be opened">
      <Alert tone="danger" title="The link is not valid" actions={<ButtonLink to="/wallet/scan" size="sm" variant="secondary">Open Receive or share</ButtonLink>}>
        Ask the verifier for a new QR code.
      </Alert>
    </Page>
  );
};

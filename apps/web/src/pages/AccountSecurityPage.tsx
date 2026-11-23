import React from "react";
import { Page } from "../components/ui/PageHeader.tsx";
import { AuthenticatorCard } from "../components/ssi/AuthenticatorCard.tsx";
import { PasswordCard, SecurityKeyCard } from "../components/ssi/AccountSecurityCards.tsx";

/** Sign-in protection is the same for every role, so it lives outside the wallet. */
export const AccountSecurityPage: React.FC = () => (
  <Page
    eyebrow="Account"
    title="Account security"
    description="Your authenticator, passkey and password."
  >
    <AuthenticatorCard />
    <SecurityKeyCard />
    <PasswordCard />
  </Page>
);

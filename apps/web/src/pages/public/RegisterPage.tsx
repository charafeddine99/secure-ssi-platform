import React from "react";
import { Link, useSearchParams } from "react-router-dom";
import { registerAccount, type RegistrationRole } from "../../api/registration.ts";
import { BrandMark } from "../../components/ssi/BrandMark.tsx";
import { Alert } from "../../components/ui/Alert.tsx";
import { Button } from "../../components/ui/Button.tsx";
import { TextAreaField, TextField } from "../../components/ui/Field.tsx";
import { describeError } from "../../lib/http.ts";

const ROLE_NOTES: Record<RegistrationRole, string> = {
  holder: "For people who keep credentials in a wallet. You can sign in straight away.",
  issuer: "For organisations that issue credentials. An administrator reviews your application first.",
  verifier: "For organisations that check credentials. An administrator reviews your application first.",
  admin: "Administrator accounts need an invitation from another administrator.",
};

export const RegisterPage: React.FC = () => {
  const [params] = useSearchParams();
  const invitationCode = params.get("invite") ?? "";
  // Public sign-up is personal only; issuer and verifier access comes from an approved organization.
  const role: RegistrationRole = invitationCode ? "admin" : "holder";
  const [email, setEmail] = React.useState("");
  const [displayName, setDisplayName] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [organization, setOrganization] = React.useState("");
  const [purpose, setPurpose] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [done, setDone] = React.useState<string | null>(null);
  const applies: boolean = false; // organization applications moved to the Organizations page

  React.useEffect(() => { document.title = "Create account · Secure SSI Platform"; }, []);

  const onSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setDone(await registerAccount({
        email: email.trim(),
        displayName: displayName.trim(),
        password,
        role,
        ...(applies ? { organization: organization.trim(), purpose: purpose.trim() } : {}),
        ...(role === "admin" ? { invitationCode } : {}),
      }));
    } catch (cause) {
      setError(describeError(cause));
    } finally {
      setPassword("");
      setBusy(false);
    }
  };

  return (
    <div className="page page-center">
      <main id="main" tabIndex={-1} className="container container-tight py-4">
        <div className="mb-4 d-flex justify-content-center"><BrandMark /></div>
        <div className="card card-md">
          <div className="card-body">
            <h1 className="h2 text-center mb-4">Create your account</h1>
            {done ? (
              <>
                <Alert tone="success" live="polite" title="Request received" className="mb-3">{done}</Alert>
                <Link className="btn btn-primary w-100" to="/login">Go to sign in</Link>
              </>
            ) : (
              <form onSubmit={onSubmit}>
                {error && <Alert tone="danger" live="assertive" title="Account not created" className="mb-3">{error}</Alert>}
                {invitationCode ? (
                  <p className="text-secondary">{ROLE_NOTES.admin}</p>
                ) : (
                  <p className="text-secondary">
                    This creates your personal account and wallet. To act for a university, company or other institution,
                    sign in afterwards and apply for it, or accept its invitation, on the Organizations page.
                  </p>
                )}
                <TextField label="Full name" autoComplete="name" value={displayName} onChange={(e) => setDisplayName(e.target.value)} maxLength={200} required />
                <TextField label="E-mail address" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} maxLength={254} required />
                <TextField label="Password" type="password" autoComplete="new-password" hint="At least 15 characters. A long phrase works well." value={password} onChange={(e) => setPassword(e.target.value)} required />
                {applies && (
                  <>
                    <TextField label="Organisation" autoComplete="organization" value={organization} onChange={(e) => setOrganization(e.target.value)} maxLength={200} required />
                    <TextAreaField label="Why you need this role" value={purpose} onChange={(e) => setPurpose(e.target.value)} maxLength={500} required />
                  </>
                )}
                <div className="form-footer">
                  <Button type="submit" block loading={busy} disabled={password.length < 15 || !email.trim() || displayName.trim().length < 2 || (applies && (organization.trim().length < 2 || purpose.trim().length < 3))}>
                    {applies ? "Send application" : "Create account"}
                  </Button>
                </div>
              </form>
            )}
          </div>
        </div>
        <div className="text-center text-secondary mt-3">Already have an account? <Link className="text-decoration-underline" to="/login">Sign in</Link></div>
      </main>
    </div>
  );
};

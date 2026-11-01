import React from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { IconCircleCheck, IconLogin2, IconPalette } from "@tabler/icons-react";
import { Alert } from "../../components/ui/Alert.tsx";
import { Button } from "../../components/ui/Button.tsx";
import { TextField } from "../../components/ui/Field.tsx";
import { BrandMark } from "../../components/ssi/BrandMark.tsx";
import { useAuth } from "../../context/AuthContext.ts";
import { roleHomePath } from "../../routes/navigation.ts";
import { useAppearance, useArtArea } from "../../theme/appearance.ts";
import { ModeToggle } from "../../theme/ModeToggle.tsx";

const POINTS = ["W3C Verifiable Credentials 2.0", "OpenID4VCI and OpenID4VP", "Every verification check shown separately"];

/** Tabler sign-in-cover layout: form column + brand artwork column. */
export const LoginPage: React.FC = () => {
  const { user, login, sessionExpired, status } = useAuth();
  const { setPanelOpen } = useAppearance();
  useArtArea("public");
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from;
  const [username, setUsername] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [errors, setErrors] = React.useState<{ username?: string; password?: string }>({});
  const [failure, setFailure] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => { document.title = "Sign in · Secure SSI Platform"; }, []);

  if (user) return <Navigate to={from && from !== "/login" ? from : roleHomePath(user.role)} replace />;

  const onSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const next: typeof errors = {};
    if (!username.trim()) next.username = "Enter your username.";
    if (!password) next.password = "Enter your password.";
    setErrors(next);
    setFailure(null);
    if (next.username || next.password) {
      document.getElementById(next.username ? "login-username" : "login-password")?.focus();
      return;
    }
    setBusy(true);
    const result = await login(username, password);
    setBusy(false);
    if (!result.ok) {
      setFailure(result.message);
      setPassword("");
    }
  };

  return (
    <div className="page">
      <div className="row g-0 flex-fill">
        <main id="main" tabIndex={-1} className="col-12 col-lg-6 col-xl-5 border-top-wide border-primary d-flex flex-column justify-content-center bg-body ssi-auth-panel">
          <div className="container ssi-auth-form my-5 px-4">
            <div className="mb-5 d-flex align-items-center justify-content-between">
              <BrandMark />
              <div className="d-flex gap-1">
                <ModeToggle className="btn-ghost-secondary" />
                <button type="button" className="btn btn-ghost-secondary btn-icon" aria-label="Appearance" onClick={() => setPanelOpen(true)}>
                  <IconPalette size={20} aria-hidden="true" />
                </button>
              </div>
            </div>
            <h1 className="h1 mb-1">Sign in</h1>
            <p className="text-secondary mb-4">Access your Secure SSI workspace.</p>
            <form onSubmit={onSubmit} noValidate aria-describedby={failure ? "login-failure" : undefined}>
              {(sessionExpired && !failure) || status === "unavailable" || failure ? (
                <div className="vstack gap-3 mb-3">
                  {sessionExpired && !failure && <Alert tone="warning" live="polite" title="Your session ended">Sign in again to continue.</Alert>}
                  {status === "unavailable" && <Alert tone="danger" live="polite" title="Identity Service unreachable">Try signing in again.</Alert>}
                  {failure && <div id="login-failure"><Alert tone="danger" live="assertive" title="Sign-in failed">{failure}</Alert></div>}
                </div>
              ) : null}
              <TextField
                label="Username"
                name="username"
                autoComplete="username"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                error={errors.username}
                required
                id="login-username"
              />
              <TextField
                label="Password"
                name="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                error={errors.password}
                required
                id="login-password"
              />
              <div className="form-footer">
                <Button type="submit" loading={busy} block icon={<IconLogin2 aria-hidden="true" />}>Sign in</Button>
              </div>
            </form>
            <div className="text-secondary mt-4 small"><Link to="/">Back to overview</Link></div>
          </div>
        </main>
        <div className="col-12 col-lg-6 col-xl-7 d-none d-lg-block">
          <div className="ssi-auth-cover h-100 min-vh-100 d-flex flex-column justify-content-end p-5">
            <h2 className="display-6 fw-bold mb-4 ssi-cover-title">Verifiable credentials you can trust.</h2>
            <ul className="list-unstyled d-flex flex-column gap-2 mb-0 fs-3">
              {POINTS.map((point) => (
                <li key={point} className="d-flex align-items-center gap-2 text-secondary-light">
                  <IconCircleCheck size={20} className="text-teal" aria-hidden="true" />{point}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

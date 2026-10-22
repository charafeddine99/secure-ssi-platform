import React, { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowRight, Building2, Check, Search, ShieldCheck, UserRound } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { roleHomePath } from "../../routes/roleNavigation";
import { BrandMark } from "../common/BrandMark";
import { Button } from "../ui/Button";

const signInProfiles: Record<string, { label: string; headline: string; summary: string; points: string[] }> = {
  holder: {
    label: "Individual user",
    headline: "Your credentials, ready when you need them.",
    summary: "Review credentials in your wallet and approve presentation requests.",
    points: ["Review credentials in your wallet", "Review each presentation request", "Manage available account security"]
  },
  issuer: {
    label: "Issuer institution",
    headline: "Create and manage credential offers.",
    summary: "Work with the configured credential metadata and offer-status workflows.",
    points: ["Review configured credential metadata", "Create credential offers", "Review returned credential status"]
  },
  verifier: {
    label: "Verifier institution",
    headline: "Verify presentations with clarity.",
    summary: "Create presentation requests and review the result returned by the service.",
    points: ["Create presentation requests", "Review returned verification results", "See current service status"]
  },
  admin: {
    label: "Platform administration",
    headline: "Platform operations, in one workspace.",
    summary: "Review service health, available access administration and audit activity.",
    points: ["Monitor connected services", "Review audit activity", "Manage permitted operations"]
  }
};

const profileOptions = [
  { key: "holder", label: "Individual", icon: UserRound },
  { key: "issuer", label: "Issuer", icon: Building2 },
  { key: "verifier", label: "Verifier", icon: Search },
  { key: "admin", label: "Admin", icon: ShieldCheck }
] as const;

export const AuthPage: React.FC = () => {
  const { login, isAuthLoading, isAuthenticated, user } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [errorKind, setErrorKind] = useState<"validation" | "credentials" | "service" | null>(null);
  const profileKey = searchParams.get("profile") ?? "";
  const selectedProfile = signInProfiles[profileKey];

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "instant" });
  }, [profileKey]);

  useEffect(() => {
    if (isAuthenticated && user) {
      navigate(roleHomePath(user.role), { replace: true });
    }
  }, [isAuthenticated, navigate, user]);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setErrorKind(null);

    if (!username.trim() || !password) {
      setError("Enter your email or username and password.");
      setErrorKind("validation");
      return;
    }

    try {
      const success = await login(username, password);
      if (!success) {
        setError("We could not sign you in. Check your account details and try again.");
        setErrorKind("credentials");
      }
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "";
      if (/identity service is unavailable|identity service request failed/i.test(message)) {
        setError("The sign-in service could not be reached. Check that the API Gateway and Identity Service are running, then retry.");
      } else {
        setError("The sign-in service returned an error. Check the service status and try again.");
      }
      setErrorKind("service");
    }
  };

  return (
    <section className="auth-page" aria-labelledby="auth-title">
      <div className="auth-layout">
        <div className="auth-card">
          <div className="auth-brand-mark" aria-hidden="true">
            <BrandMark size={34} />
          </div>

          <header className="auth-heading">
            {selectedProfile && <p className="auth-profile-label">{selectedProfile.label}</p>}
            <h1 id="auth-title">Sign in</h1>
            <p>Use your account to continue.</p>
          </header>

          <div className="auth-profile-picker">
            <p className="auth-profile-picker-label">Choose a sign-in area</p>
            <nav className="auth-profile-options" aria-label="Sign-in areas">
              {profileOptions.map(({ key, label, icon: Icon }) => (
                <Link
                  key={key}
                  to={`/login?profile=${key}`}
                  className="auth-profile-option"
                  aria-current={profileKey === key ? "page" : undefined}
                >
                  <Icon size={17} aria-hidden="true" />
                  <span>{label}</span>
                </Link>
              ))}
            </nav>
            <p className="auth-profile-hint">Your assigned access is checked at sign-in.</p>
          </div>

          <form className="auth-form" onSubmit={handleSubmit} noValidate>
            {error && (
              <div id="auth-error" className="auth-error" role="alert">
                {error}
              </div>
            )}

            <div className="auth-field">
              <label htmlFor="auth-username">Email or username</label>
              <input
                id="auth-username"
                name="username"
                type="text"
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
                required
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                placeholder="name@organization.com"
                aria-invalid={errorKind === "validation" || errorKind === "credentials"}
                aria-describedby={error ? "auth-error" : undefined}
                className="ui-input auth-input"
              />
            </div>

            <div className="auth-field">
              <label htmlFor="auth-password">Password</label>
              <input
                id="auth-password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Enter your password"
                aria-invalid={errorKind === "validation" || errorKind === "credentials"}
                aria-describedby={error ? "auth-error" : undefined}
                className="ui-input auth-input"
              />
            </div>

            <Button className="auth-submit" type="submit" size="large" disabled={isAuthLoading}>
              <span>{isAuthLoading ? "Signing in…" : "Sign in"}</span>
              {!isAuthLoading && <ArrowRight size={17} aria-hidden="true" />}
            </Button>
          </form>
        </div>

        <aside className="auth-visual" aria-labelledby="auth-visual-title">
          <div className="auth-visual-content">
            <p className="auth-visual-kicker"><ShieldCheck size={15} aria-hidden="true" /> Secure identity workflows</p>
            <h2 id="auth-visual-title">
              {selectedProfile?.headline ?? "Digital credentials, managed with clarity."}
            </h2>
            <p className="auth-visual-summary">
              {selectedProfile?.summary ?? "Issue, manage and verify credentials through one connected platform."}
            </p>
            <ul className="auth-visual-points">
              {(selectedProfile?.points ?? ["Issue trusted credentials", "Choose what to share", "Verify each presentation"]).map((point) => (
                <li key={point}><span><Check size={14} aria-hidden="true" /></span>{point}</li>
              ))}
            </ul>
            <div className="auth-visual-footer">
              <BrandMark size={30} />
              <span>Workspace access follows your account permissions.</span>
            </div>
          </div>
        </aside>
      </div>
    </section>
  );
};

import React from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Building2, KeyRound, Search, ShieldCheck, UserRound } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { roleHomePath } from "../../routes/roleNavigation";
import { ButtonLink } from "../../components/ui/Button";

const workflows = [
  {
    step: "01",
    title: "Issue",
    description: "Create offers from configured credential metadata.",
    icon: Building2
  },
  {
    step: "02",
    title: "Manage",
    description: "Review received credentials and approve requests.",
    icon: KeyRound
  },
  {
    step: "03",
    title: "Verify",
    description: "Create requests and review returned results.",
    icon: Search
  }
];

const workspaceEntries = [
  {
    profile: "holder",
    title: "Holder / Individual user",
    description: "View your credentials and approve presentation requests.",
    icon: UserRound
  },
  {
    profile: "issuer",
    title: "Issuer institution",
    role: "Issuer",
    description: "Create credential offers and review credential status.",
    icon: Building2
  },
  {
    profile: "verifier",
    title: "Verifier institution",
    role: "Verifier",
    description: "Create requests and review returned verification results.",
    icon: Search
  },
  {
    profile: "admin",
    title: "Platform administration",
    role: "Admin",
    description: "Review service health and permitted platform operations.",
    icon: ShieldCheck
  }
] as const;

export const LandingPage: React.FC = () => {
  const { isAuthenticated, user } = useAuth();
  const primaryPath = isAuthenticated && user ? roleHomePath(user.role) : "/login";
  // The profile query only selects the sign-in context. AuthPage still redirects
  // an authenticated account to its server-derived workspace.
  const entryPath = (profile: string) => `/login?profile=${profile}`;

  return (
    <div className="landing-page">
      <section className="landing-hero" aria-labelledby="landing-title">
        <div className="landing-hero-backdrop" aria-hidden="true" />
        <div className="landing-hero-copy">
          <p className="landing-eyebrow">
            <ShieldCheck size={16} aria-hidden="true" />
            Secure identity workflows
          </p>
          <h1 id="landing-title" className="landing-hero-title">
            A clearer way to issue, hold and verify credentials.
          </h1>
          <p className="landing-hero-description">
            One workspace for credential offers, wallet consent and presentation verification.
          </p>
          <div className="landing-hero-actions">
            <ButtonLink className="landing-primary-action" to={primaryPath} size="large">
              {isAuthenticated ? "Open your workspace" : "Sign in"}
              <ArrowRight size={17} aria-hidden="true" />
            </ButtonLink>
            <ButtonLink className="landing-secondary-action" to="/ecosystem" variant="secondary">
              Explore the platform
            </ButtonLink>
          </div>
        </div>

        <section className="landing-workflow-card" aria-labelledby="landing-workflow-title">
          <div className="landing-workflow-heading">
            <div>
              <span className="landing-workflow-kicker">Credential lifecycle</span>
              <h2 id="landing-workflow-title">From offer to verification</h2>
            </div>
            <span className="landing-workflow-mark" aria-hidden="true">
              <ShieldCheck size={21} />
            </span>
          </div>
          <ol className="landing-workflow-list">
            {workflows.map(({ step, title, description, icon: Icon }) => (
              <li key={step}>
                <span className="landing-workflow-step">{step}</span>
                <span className="landing-workflow-icon" aria-hidden="true"><Icon size={18} /></span>
                <span className="landing-workflow-text">
                  <strong>{title}</strong>
                  <span>{description}</span>
                </span>
              </li>
            ))}
          </ol>
        </section>
      </section>

      <section className="landing-entry-section" id="workspace-entry-points" aria-labelledby="workspace-entry-title">
        <div className="landing-entry-heading">
          <div>
            <p className="landing-eyebrow">Workspaces</p>
            <h2 id="workspace-entry-title">Choose where to sign in</h2>
          </div>
          <p>Your account’s assigned access determines the workspace you can use.</p>
        </div>
        <div className="landing-entry-grid">
          {workspaceEntries.map(({ profile, title, description, icon: Icon }) => (
            <Link className="landing-entry-card" key={profile} to={entryPath(profile)}>
              <span className="landing-entry-card-icon" aria-hidden="true"><Icon size={19} /></span>
              <span className="landing-entry-card-copy">
                <strong>{title}</strong>
                <span>{description}</span>
              </span>
              <ArrowRight className="landing-entry-arrow" size={17} aria-hidden="true" />
            </Link>
          ))}
        </div>
        <p className="landing-entry-security-note">
          Selecting an entry only opens sign-in. The server verifies your role and permissions.
        </p>
      </section>
    </div>
  );
};

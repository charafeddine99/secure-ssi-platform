import React from "react";
import { IconArrowRight, IconBuildingBank, IconKey, IconUserCheck, IconUserSearch } from "@tabler/icons-react";
import { ButtonLink } from "../../components/ui/Button.tsx";
import { Grid } from "../../components/ui/PageHeader.tsx";
import { useAuth } from "../../context/AuthContext.ts";
import { roleHomePath } from "../../routes/navigation.ts";
import { TrustTriangle } from "../../components/ssi/TrustTriangle.tsx";

const ROLES = [
  { icon: <IconUserCheck size={22} aria-hidden="true" />, tone: "bg-primary-lt", title: "Holder", text: "Store credentials and decide what to share." },
  { icon: <IconBuildingBank size={22} aria-hidden="true" />, tone: "bg-indigo-lt", title: "Issuer", text: "Issue credentials and manage revocation." },
  { icon: <IconUserSearch size={22} aria-hidden="true" />, tone: "bg-teal-lt", title: "Verifier", text: "Request presentations and check each result." },
  { icon: <IconKey size={22} aria-hidden="true" />, tone: "bg-orange-lt", title: "Guardian", text: "Approve wallet recovery for people you trust." },
];

const LIFECYCLE = ["Issue", "Store", "Request", "Consent", "Verify"];

export const LandingPage: React.FC = () => {
  const { user } = useAuth();
  React.useEffect(() => { document.title = "Secure SSI Platform"; }, []);
  return (
    <>
      <section className="ssi-band ssi-hero" aria-labelledby="hero-title">
        <div className="ssi-band-art" aria-hidden="true" />
        <div className="container-xl">
          <div className="row">
            <div className="col-lg-7">
              <div className="page-pretitle mb-3">Self-sovereign identity</div>
              <h1 id="hero-title" className="display-5 fw-bold mb-3">Verifiable credentials <span className="ssi-gradient-text">you can trust.</span></h1>
              <p className="lead fs-2 mb-4">Issue, hold and verify W3C credentials with OpenID4VCI and OpenID4VP.</p>
              <div className="btn-list">
                {user
                  ? <ButtonLink to={roleHomePath(user.role)} icon={<IconArrowRight aria-hidden="true" />}>Open workspace</ButtonLink>
                  : <><ButtonLink to="/register" icon={<IconArrowRight aria-hidden="true" />}>Create account</ButtonLink><ButtonLink to="/login" variant="secondary">Sign in</ButtonLink></>}
                <ButtonLink to="/docs" variant="secondary">How it works</ButtonLink>
              </div>
            </div>
          </div>
        </div>
      </section>

      <div className="page-body ssi-band-body">
        <div className="container-xl">
          <div className="vstack gap-4">
            <Grid cols={4}>
              {ROLES.map((role) => (
                <article key={role.title} className="card">
                  <div className="card-body">
                    <span className={`avatar avatar-md ${role.tone} mb-3`} aria-hidden="true">{role.icon}</span>
                    <h2 className="card-title mb-1">{role.title}</h2>
                    <p className="text-secondary mb-0">{role.text}</p>
                  </div>
                </article>
              ))}
            </Grid>

            <section className="card ssi-triangle-card" aria-labelledby="triangle-heading">
              <div className="card-body p-4 p-lg-5">
                <div className="row g-4 align-items-center">
                  <div className="col-lg-5">
                    <div className="page-pretitle mb-2">How trust works</div>
                    <h2 id="triangle-heading" className="h1 mb-3">Three roles, one verifiable chain.</h2>
                    <ul className="list-unstyled vstack gap-3 mb-0">
                      <li className="d-flex gap-3"><span className="ssi-dot" />The issuer signs a credential with its key.</li>
                      <li className="d-flex gap-3"><span className="ssi-dot" />The holder keeps it and decides when to share.</li>
                      <li className="d-flex gap-3"><span className="ssi-dot" />The verifier checks the signature and the issuer in the Trust Registry.</li>
                    </ul>
                  </div>
                  <div className="col-lg-7"><TrustTriangle /></div>
                </div>
              </div>
            </section>

            <section className="card" aria-labelledby="lifecycle-title">
              <div className="card-body">
                <h2 id="lifecycle-title" className="subheader mb-3">Credential lifecycle</h2>
                <ol className="steps steps-counter steps-blue mb-0">
                  {LIFECYCLE.map((step) => <li key={step} className="step-item">{step}</li>)}
                </ol>
              </div>
            </section>
          </div>
        </div>
      </div>
    </>
  );
};

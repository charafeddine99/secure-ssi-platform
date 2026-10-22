import React from "react";

const layers = [
  {
    label: "Optional integrity",
    title: "Blockchain anchoring",
    technology: "Solidity 0.8.28 · optional EVM connection",
    description: "Contract sources and an optional hash-anchoring bridge are present. Credential trust, signature and status decisions remain off-chain; deployment and transaction receipts are not asserted.",
    artifacts: [
      { name: "DIDRegistry.sol", description: "Optional DID and hash registry; not the authoritative issuer trust registry." },
      { name: "EmergencyRecovery.sol", description: "Contract source only; recovery workflows run in the Recovery Service." },
      { name: "RevocationRegistry.sol", description: "Optional integrity anchor; W3C status-list checks remain authoritative." },
      { name: "AuditLogger.sol", description: "Optional integrity log; application audit events remain in service persistence." },
    ],
  },
  {
    label: "Risk service",
    title: "Advisory risk assessment",
    technology: "Python 3.11 · FastAPI · port 8002",
    description: "A deterministic heuristic evaluates prototype signals. Inputs are synthetic, the result is advisory, and no trained model or independent labelled evaluation is claimed.",
    endpoints: [
      { method: "POST", path: "/api/v1/fraud/evaluate", description: "Evaluate supplied prototype signals and return a versioned score with reasons." },
      { method: "GET", path: "/health", description: "Check Fraud Service health." },
    ],
  },
  {
    label: "SSI Core",
    title: "Identity and credential services",
    technology: "Python 3.11 · FastAPI · MongoDB",
    description: "Implements the project’s VC Data Model 2.0 profile, wallet-bound issuance, OID4VP/DCQL, trust checks and Bitstring Status List 1.0. Local key adapters and resolver fixtures remain prototype infrastructure.",
    endpoints: [
      { method: "POST", path: "/api/v1/oid4vci/token", description: "Redeem a pre-authorized offer and return an access token and nonce." },
      { method: "POST", path: "/api/v1/oid4vci/credential", description: "Issue a credential after token and holder-proof validation." },
      { method: "POST", path: "/api/v1/oid4vp/requests", description: "Create a presentation request and server-bound DCQL session." },
      { method: "POST", path: "/api/v1/oid4vp/response", description: "Evaluate a verifier response using backend policy." },
    ],
  },
  {
    label: "Application access",
    title: "API Gateway and web application",
    technology: "FastAPI · React 18 · TypeScript · Vite",
    description: "The browser uses the API Gateway for Identity, Fraud, Recovery and system-health routes. Holder, issuer, verifier, guardian and admin workspaces expose role-specific flows.",
    endpoints: [
      { method: "GET", path: "/api/v1/system/status", description: "Return aggregate service health and optional blockchain connectivity." },
      { method: "ALL", path: "/api/v1/identity/*", description: "Proxy requests to SSI Core (port 8001)." },
      { method: "ALL", path: "/api/v1/fraud/*", description: "Proxy requests to the Fraud Service (port 8002)." },
      { method: "ALL", path: "/api/v1/recovery/*", description: "Proxy requests to the Recovery Service (port 8003)." },
    ],
  },
];

export const ArchitectureDocsPage: React.FC = () => (
  <main className="public-docs-page">
    <header className="public-docs-intro">
      <p className="workspace-eyebrow">Technical overview</p>
      <h1>Platform architecture</h1>
      <p>Core identity, risk and application services, with optional integrity anchoring. Expand a section for its API routes or source files.</p>
    </header>

    <div className="public-docs-grid">
      {layers.map((layer) => (
        <article className="public-docs-card" key={layer.title}>
          <header className="public-docs-card__heading">
            <div className="public-docs-card__identity">
              <p className="public-docs-card__eyebrow">{layer.label}</p>
              <h2>{layer.title}</h2>
            </div>
            <span className="public-docs-card__tech">{layer.technology}</span>
          </header>
          <p>{layer.description}</p>

          {"artifacts" in layer && layer.artifacts && (
            <details>
              <summary>Contract source files</summary>
              <div className="public-docs-artifacts">
                {layer.artifacts.map((artifact) => (
                  <div className="public-docs-artifact" key={artifact.name}>
                    <strong>{artifact.name}</strong>
                    <span>{artifact.description}</span>
                  </div>
                ))}
              </div>
            </details>
          )}

          {"endpoints" in layer && layer.endpoints && (
            <details>
              <summary>API routes</summary>
              <div className="public-docs-endpoints">
                {layer.endpoints.map((endpoint) => (
                  <div className="public-docs-endpoint" key={`${endpoint.method}:${endpoint.path}`}>
                    <span className="public-docs-method">{endpoint.method}</span>
                    <code>{endpoint.path}</code>
                    <span>{endpoint.description}</span>
                  </div>
                ))}
              </div>
            </details>
          )}
        </article>
      ))}
    </div>
  </main>
);

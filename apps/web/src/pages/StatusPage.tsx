import { ModuleCard } from "../components/ModuleCard";
import type { SystemModule } from "../types/system";

const modules: SystemModule[] = [
  { name: "Identity Service", description: "DID and credential capabilities are planned." },
  { name: "Fraud Detection Service", description: "AI-based risk analysis is planned." },
  { name: "Blockchain Service", description: "Smart contract capabilities are planned." },
  { name: "Emergency Recovery Service", description: "Guardian recovery workflows are planned." },
];

export function StatusPage() {
  return (
    <main>
      <header className="hero">
        <span className="eyebrow">Academic prototype · v0.1.0</span>
        <h1>Secure Self-Sovereign Identity</h1>
        <p>AI-based fraud detection and emergency recovery on blockchain.</p>
      </header>
      <section aria-labelledby="system-status">
        <h2 id="system-status">System status</h2>
        <p className="section-intro">Core service boundaries are being prepared.</p>
        <div className="module-grid">
          {modules.map((module) => <ModuleCard key={module.name} module={module} />)}
        </div>
      </section>
    </main>
  );
}

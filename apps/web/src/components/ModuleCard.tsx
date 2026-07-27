import type { SystemModule } from "../types/system";

export function ModuleCard({ module }: { module: SystemModule }) {
  return (
    <article className="module-card">
      <div className="status-indicator" aria-hidden="true" />
      <h3>{module.name}</h3>
      <p>{module.description}</p>
      <span className="status-label">Setup in progress</span>
    </article>
  );
}

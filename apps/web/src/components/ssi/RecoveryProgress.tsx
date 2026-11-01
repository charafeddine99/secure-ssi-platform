import React from "react";
import type { RecoveryRequest } from "../../api/recovery.ts";
import { formatDateTime } from "../../lib/format.ts";

type StepState = "done" | "current" | "pending" | "failed";

const STATE_TEXT: Record<StepState, string> = { done: "completed", current: "in progress", pending: "not started", failed: "stopped" };

/** Request → guardian approvals → time-lock → managed key rotation, as Tabler vertical steps. */
export const RecoveryProgress: React.FC<{ request: RecoveryRequest }> = ({ request }) => {
  const s = request.status;
  const failed = ["REJECTED", "CANCELLED", "EXPIRED", "FAILED"].includes(s);
  const order = ["PENDING_APPROVALS", "QUORUM_REACHED", "WAITING_TIMELOCK", "READY_FOR_EXECUTION", "EXECUTING", "COMPLETED"];
  const index = order.indexOf(s);
  const stage = (stageIndex: number): StepState => {
    if (s === "COMPLETED") return "done";
    if (failed) return stageIndex === 0 ? "done" : "failed";
    if (index > stageIndex) return "done";
    if (index === stageIndex) return "current";
    return "pending";
  };
  const approvals = request.approvalsCount ?? 0;
  const required = request.requiredCount ?? 0;
  const percent = required > 0 ? Math.min(100, Math.round((approvals / required) * 100)) : 0;
  const steps: Array<{ title: string; detail: React.ReactNode; state: StepState }> = [
    { title: "Recovery requested", detail: formatDateTime(request.createdAt), state: "done" },
    {
      title: "Guardian approvals",
      state: index >= 1 || s === "COMPLETED" ? "done" : failed ? "failed" : "current",
      detail: (
        <>
          <span className="d-block mb-1">{approvals} of {required || "?"} required approvals{request.rejectionsCount ? ` · ${request.rejectionsCount} rejected` : ""}</span>
          <div className="progress progress-sm" role="progressbar" aria-valuemin={0} aria-valuemax={required || 1} aria-valuenow={approvals} aria-label="Guardian approvals">
            <div className="progress-bar bg-primary" style={{ width: `${percent}%` }} />
          </div>
        </>
      ),
    },
    {
      title: "Time-lock",
      state: stage(2),
      detail: request.timelockExpiresAt ? `Executable after ${formatDateTime(request.timelockExpiresAt)}` : "Starts after quorum",
    },
    {
      title: "Managed key rotation",
      state: s === "COMPLETED" ? "done" : s === "EXECUTING" ? "current" : failed ? "failed" : "pending",
      detail: request.result
        ? `Completed ${formatDateTime(request.result.completedAt)}. A successor key and DID replaced the predecessor.`
        : "Not performed yet. Guardian approval alone does not change any key.",
    },
  ];
  const current = steps.findIndex((step) => step.state === "current" || step.state === "failed");
  const activeIndex = current === -1 ? steps.length - 1 : current;
  return (
    <ol className={["steps steps-vertical mb-0", failed ? "steps-red" : "steps-blue"].join(" ")} aria-label="Recovery progress">
      {steps.map((step, i) => (
        <li key={step.title} className={["step-item", i === activeIndex ? "active" : ""].filter(Boolean).join(" ")} aria-current={i === activeIndex ? "step" : undefined}>
          <div className="h4 m-0">
            {step.title}
            <span className="visually-hidden"> — {STATE_TEXT[step.state]}</span>
          </div>
          <div className="text-secondary small">{step.detail}</div>
        </li>
      ))}
    </ol>
  );
};

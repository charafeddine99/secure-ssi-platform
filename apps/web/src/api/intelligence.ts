import { apiRequest, assertShape } from "../lib/http.ts";
import { stepUpHeaders } from "./stepUp.ts";

const BASE = "/api/v1/fraud/intel";

export type Origin = "OPERATIONAL" | "SYNTHETIC_TEST";

export interface SourceHealth {
  source: string;
  state: string;
  last_seen_at: string | null;
  age_seconds: number | null;
  backlog: number | null;
  dropped: number | null;
  rejected: number | null;
  accepted: number | null;
  delivery_failures: number | null;
}
export interface DomainCoverage { domain: string; producer: string; expected: string[]; observed: string[]; state: string }
export interface Monitoring { numerator: number; denominator: number; percent: number; domains: DomainCoverage[] }
export interface IntelHealth {
  store: string;
  origin: Origin;
  as_of: string;
  state: string;
  sources: SourceHealth[];
  last_event_lag_seconds: number | null;
  monitoring: Monitoring;
}
export interface Rate {
  name: string;
  unit: string;
  numerator: number;
  denominator: number;
  numerator_types: string[];
  denominator_types: string[];
  value: number | null;
}
export interface IntelMetrics {
  origin: Origin;
  as_of: string;
  hours: number;
  window_start: string;
  window_end: string;
  rates: Rate[];
  raw_signals_by_category: { category: string; count: number }[];
  event_counts: { event_type: string; count: number }[];
  hourly: { hour: string; signals: number }[];
}
export interface AnomalySeries {
  series: string;
  event_types: string[];
  method: string;
  state: string;
  baseline_hours: number;
  required_hours: number;
  current_hour: string;
  current_count: number;
  threshold: number;
  minimum_count: number;
  median: number | null;
  mad: number | null;
  modified_z: number | null;
}
export interface IntelAnomalies { origin: Origin; as_of: string; method: string; baseline_days: number; series: AnomalySeries[] }
export interface IncidentHistory { status: string; at: string; by: string; note: string }
export interface Incident {
  incident_id: string;
  status: string;
  next_statuses: string[];
  detection_state: string;
  origin: Origin;
  rule_id: string;
  rule_version: string;
  title: string;
  category: string;
  severity: string;
  confidence: string;
  explanation: string;
  service: string;
  subject_ref: string;
  threshold: number;
  window_seconds: number;
  observed_count: number;
  signal_count: number;
  suppressed_alerts: number;
  event_refs: string[];
  first_observed_at: string;
  last_observed_at: string;
  delivery: string;
  owner?: string;
  history: IncidentHistory[];
}
export interface Assessment {
  assessment_type: string;
  subject_scope: string;
  risk_score: number;
  risk_level: string;
  assessment_mode: string;
  reason_codes: string[];
  data_quality: string;
  rule_version: string;
  recommended_action: string;
  assessed_at: string;
}
export interface RiskSummary {
  hours: number;
  assessments: number;
  truncated: boolean;
  levels: Record<string, number>;
  types: Record<string, number>;
  score_semantics: string;
  recent: Assessment[];
}
export interface Rule {
  rule_id: string;
  title: string;
  category: string;
  state: string;
  severity: string;
  confidence: string;
  trigger: string[];
  counted: string[];
  group: string;
  threshold: number;
  window_seconds: number;
  attack: string[];
  reference: string;
  explanation: string;
}
export interface RuleSet { ruleset_version: string; change_control: string; event_types: number; rules: Rule[] }
export interface Measure { numerator: number; denominator: number; percent: number | null }
export interface Posture {
  origin: Origin;
  as_of: string;
  matrix_version: string;
  generated_on: string;
  source: string;
  evidence_review_days: number;
  implementation_coverage: Measure;
  verified_control_coverage: Measure;
  evidence_freshness: Measure;
  test_pass_rate: Measure & { failed: number; skipped: number; not_run: string[] };
  monitoring_coverage: Monitoring | null;
  open_findings: {
    by_priority: Record<string, number>;
    critical_and_high: { id: string; priority: string; finding: string; status: string }[];
  };
  not_verified: { id: string; level: string; gap: string }[];
}
export interface ModelStatus {
  model_status: string;
  training_data_status: string;
  detection_mode: string;
  origin: Origin;
  reviewed_labels: Record<string, number>;
  metrics: null;
  explanation: string;
}

function query(origin: Origin | null, extra: Record<string, string> = {}): string {
  const params = new URLSearchParams(extra);
  if (origin) params.set("origin", origin);
  const text = params.toString();
  return text ? `?${text}` : "";
}

async function read<T>(path: string): Promise<T> {
  const body = await apiRequest<T>(`${BASE}/${path}`);
  assertShape(body && typeof body === "object", `intelligence ${path}`);
  return body;
}

export const fetchIntelHealth = (origin: Origin | null) => read<IntelHealth>(`health${query(origin)}`);
export const fetchIntelMetrics = (origin: Origin | null, hours: number) => read<IntelMetrics>(`metrics${query(origin, { hours: String(hours) })}`);
export const fetchIntelAnomalies = (origin: Origin | null) => read<IntelAnomalies>(`anomalies${query(origin)}`);
export const fetchIntelRisk = (hours: number) => read<RiskSummary>(`risk?hours=${hours}`);
export const fetchIntelRules = () => read<RuleSet>("rules");
export const fetchIntelPosture = (origin: Origin | null) => read<Posture>(`posture${query(origin)}`);
export const fetchIntelModel = (origin: Origin | null) => read<ModelStatus>(`model${query(origin)}`);

export async function fetchIncidents(origin: Origin | null): Promise<{ origin: Origin; items: Incident[] }> {
  const body = await read<{ origin: Origin; items: Incident[] }>(`incidents${query(origin, { limit: "100" })}`);
  assertShape(Array.isArray(body.items), "incident list");
  return body;
}

export function transitionIncident(incidentId: string, status: string, note: string, stepUpToken: string | null): Promise<Incident> {
  return apiRequest<Incident>(`${BASE}/incidents/${encodeURIComponent(incidentId)}/transition`, {
    method: "POST",
    body: { status, note },
    headers: stepUpHeaders(stepUpToken),
  });
}

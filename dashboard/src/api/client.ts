// Typed API client for the Canary backend. Types mirror the pydantic models in
// backend/src/canary_server/models.py. In dev, Vite proxies /v1 to :8732; in
// production the SPA is served from the same origin as the API.

export interface RunSummary {
  run_id: string;
  agent: string;
  service: string;
  status: "ok" | "error";
  start_time: number;
  end_time: number | null;
  duration_ms: number | null;
  task: unknown;
  span_count: number;
  error_count: number;
  cost_usd: number;
  error_type: string | null;
}

export interface SpanOut {
  span_id: string;
  run_id: string;
  parent_id: string | null;
  name: string;
  kind: "run" | "llm" | "tool" | "span";
  status: "ok" | "error";
  start_time: number;
  end_time: number | null;
  duration_ms: number | null;
  attributes: Record<string, unknown>;
  input: unknown;
  output: unknown;
  error: {
    type: string;
    message: string;
    traceback: string;
    failed_at: string;
    fingerprint: string;
  } | null;
}

export interface Thought {
  thought: string;
  action: string | null;
  observation: string | null;
}

export interface RunDetail {
  run: RunSummary;
  spans: SpanOut[];
  thoughts: Thought[];
}

export interface ErrorGroup {
  fingerprint: string;
  error_type: string;
  sample_message: string;
  tool: string | null;
  agent: string | null;
  count: number;
  first_seen: number;
  last_seen: number;
  affected_agents: string[];
  affected_tools: string[];
  sample_run_id: string | null;
}

export interface TrendPoint {
  date: string;
  runs: number;
  errors: number;
}

export interface NameCount {
  name: string;
  total: number;
  errors: number;
  error_rate: number;
}

export interface Stats {
  total_runs: number;
  success_rate: number;
  error_rate: number;
  avg_latency_ms: number;
  total_cost_usd: number;
  trend: TrendPoint[];
  top_failing_tools: NameCount[];
  top_failing_agents: NameCount[];
}

export interface AlertScope {
  tool: string | null;
  agent: string | null;
}

export interface AlertRule {
  id: string;
  name: string;
  condition: string;
  scope: AlertScope;
  window_minutes: number;
  channel: string;
  webhook_url: string | null;
  enabled: boolean;
  created_at: number;
}

export interface AlertFiring {
  id: string;
  rule_id: string;
  rule_name: string;
  fired_at: number;
  value: number;
  message: string;
}

export interface AlertsResponse {
  rules: AlertRule[];
  recent_firings: AlertFiring[];
}

export interface NewAlertRule {
  name: string;
  condition: string;
  scope: { tool?: string | null; agent?: string | null };
  window_minutes: number;
  channel: string;
  webhook_url?: string | null;
  enabled: boolean;
}

/** Thin fetch wrapper that throws on non-2xx and parses JSON. */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* body wasn't JSON */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

function qs(params: Record<string, string | number | undefined>): string {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== "");
  if (!entries.length) return "";
  return "?" + entries.map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join("&");
}

export const api = {
  listRuns: (filters: { agent?: string; status?: string; limit?: number } = {}) =>
    request<RunSummary[]>(`/v1/runs${qs(filters)}`),
  getRun: (id: string) => request<RunDetail>(`/v1/runs/${id}`),
  listErrors: (filters: { agent?: string; tool?: string } = {}) =>
    request<ErrorGroup[]>(`/v1/errors${qs(filters)}`),
  stats: (days = 7) => request<Stats>(`/v1/stats${qs({ days })}`),
  alerts: () => request<AlertsResponse>(`/v1/alerts`),
  createAlert: (rule: NewAlertRule) =>
    request<AlertRule>(`/v1/alerts`, { method: "POST", body: JSON.stringify(rule) }),
};

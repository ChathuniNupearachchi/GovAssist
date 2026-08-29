// admin-dashboard change: a thin fetch wrapper over /admin/api. No
// framework-specific HTTP client — an internal tool for a handful of
// staff doesn't need one, per CLAUDE.md's "keep it plain" instruction.

const BASE_URL = import.meta.env.VITE_ADMIN_API_URL ?? "http://localhost:8001";
const TOKEN_KEY = "govassist_admin_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const response = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  if (response.status === 401) {
    clearToken();
    throw new ApiError(401, "Session expired — please sign in again.");
  }
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // Response wasn't JSON — keep the status text.
    }
    throw new ApiError(response.status, detail);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

// --- Types (mirroring admin/api/app/schemas.py) ---------------------------

export interface Citation {
  source_document_id: string;
  source_url: string;
  verified_at: string | null;
}

export interface Resource {
  label: string;
  url: string;
  type: string;
}

export interface RequirementDetail {
  id: string;
  label: string;
  kind: string;
  sequence: number;
  freshness_rule: string | null;
  citation: Citation;
  resources: Resource[];
}

export interface ConditionRow {
  id: string;
  question_id: string;
  attribute: string;
  operator: string;
  value: string;
}

export interface FeeRule {
  id: string;
  basis: string;
  base_amount: number;
  currency: string;
  penalty_amount: number | null;
  condition_id: string | null;
  citation: Citation;
}

export interface QuestionDetail {
  id: string;
  prompt: string;
  answer_type: string;
  sequence: number;
  hint: string | null;
}

export interface RecentApproval {
  id: string;
  action: string;
  target_type: string;
  target_id: string;
  reason: string | null;
  admin_email: string;
  created_at: string;
}

export interface DashboardSummary {
  drafts_pending: number;
  sources_pending: number;
  services_without_approved_rule: number;
  recently_approved: RecentApproval[];
}

export interface ServiceSummary {
  id: string;
  code: string;
  name: string;
  category: string;
  requirement_count: number;
  condition_count: number;
  question_count: number;
  current_rule_version_number: number | null;
  current_rule_version_status: string | null;
  last_verified_at: string | null;
}

export interface Overlay {
  id: string;
  target_type: string;
  target_id: string | null;
  operation: "create" | "update" | "delete";
  payload: Record<string, unknown>;
  created_at: string;
}

export interface ServiceDetail extends ServiceSummary {
  requirements: RequirementDetail[];
  conditions: ConditionRow[];
  fee_rules: FeeRule[];
  questions: QuestionDetail[];
  overlays: Overlay[];
}

export interface SourceDoc {
  id: string;
  source_url: string;
  document_type: string;
  status: string;
  fetched_at: string;
  approved_at: string | null;
  content_hash: string;
  extraction_method: string | null;
  supported_services: string[];
}

export interface PendingRule {
  id: string;
  source: "admin_draft" | "rule_version";
  service_id: string;
  service_code: string;
  service_name: string;
  status: string;
  reason: string | null;
  created_at: string | null;
}

export interface RulePayload {
  requirements: Array<Record<string, unknown>>;
  fee: Record<string, unknown> | null;
  note: string | null;
}

export interface DiffEntry {
  field: string;
  approved_value: unknown;
  draft_value: unknown;
  materiality: "material" | "cosmetic";
}

export interface RuleComparison {
  pending: PendingRule;
  approved: RulePayload;
  draft: RulePayload;
  diffs: DiffEntry[];
}

export interface PlanAudit {
  case_id: string;
  service_code: string;
  service_name: string;
  resolved_at: string;
  resolved_rule_version_number: number;
  resolved_rule_version_status: string;
  current_approved_rule_version_number: number | null;
  outdated: boolean;
}

// --- Auth -------------------------------------------------------------------

export function signup(email: string, password: string, role: "reviewer" | "approver") {
  return request<{ access_token: string; token_type: string }>("/admin/auth/signup", {
    method: "POST",
    body: JSON.stringify({ email, password, role }),
  });
}

export function signin(email: string, password: string) {
  return request<{ access_token: string; token_type: string }>("/admin/auth/signin", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

// --- Dashboard ----------------------------------------------------------------

export function getDashboardSummary() {
  return request<DashboardSummary>("/admin/dashboard/summary");
}

// --- Services -------------------------------------------------------------

export function listServices() {
  return request<ServiceSummary[]>("/admin/services");
}

export function getService(id: string) {
  return request<ServiceDetail>(`/admin/services/${id}`);
}

export function writeServiceOverlay(
  serviceId: string,
  operation: "create" | "update" | "delete",
  payload: Record<string, unknown>,
) {
  return request<Overlay>(`/admin/services/${serviceId}/overlay`, {
    method: "POST",
    body: JSON.stringify({ operation, payload }),
  });
}

// --- Sources ----------------------------------------------------------------

export function listSources() {
  return request<SourceDoc[]>("/admin/sources");
}

export function addSourceOverlay(source_url: string, document_type: "html" | "pdf") {
  return request<Overlay>("/admin/sources/overlay", {
    method: "POST",
    body: JSON.stringify({ source_url, document_type }),
  });
}

// --- Rule review --------------------------------------------------------------

export function listPendingRules() {
  return request<PendingRule[]>("/admin/rules/pending");
}

export function getRuleComparison(id: string) {
  return request<RuleComparison>(`/admin/rules/pending/${id}`);
}

export function approveRule(id: string) {
  return request<PendingRule>(`/admin/rules/pending/${id}/approve`, { method: "POST" });
}

export function rejectRule(id: string, reason: string) {
  return request<PendingRule>(`/admin/rules/pending/${id}/reject`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

// --- Plan audit -----------------------------------------------------------

export function getPlanAudit() {
  return request<PlanAudit[]>("/admin/plans/audit");
}

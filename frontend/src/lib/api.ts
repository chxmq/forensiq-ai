import axios from "axios";
import { clearAuth, getToken } from "./auth";

export const api = axios.create({ baseURL: "/api" });

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401 && !err.config?.url?.includes("/auth/login")) {
      clearAuth();
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(err);
  },
);

export const login = (username: string, password: string) =>
  api.post<{ access_token: string; username: string; auth_enabled: boolean }>(
    "/auth/login",
    { username, password },
  ).then((r) => r.data);

// ── Types ────────────────────────────────────────────────────────────
export type Severity = "low" | "medium" | "high" | "critical";

export interface Finding {
  id: string;
  module: string;
  code: string;
  title: string;
  detail: string;
  severity: Severity;
  confidence: number;
  evidence: Record<string, any> | null;
  created_at: string;
}

export interface DocumentOut {
  id: string;
  doc_type: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  sha256: string | null;
  integrity_score: number;
  extracted_fields: Record<string, any> | null;
  forensics: Record<string, any> | null;
  artifacts: Record<string, any> | null;
  created_at: string;
}

export interface AuditEvent {
  id: string;
  actor: string;
  action: string;
  detail: string | null;
  created_at: string;
}

export interface CaseOut {
  id: string;
  case_number: string;
  status: string;
  priority: Severity;
  assignee: string | null;
  summary: string | null;
  resolution_note: string | null;
  application_id: string;
  applicant_name: string | null;
  application_reference: string | null;
  created_at: string;
  updated_at: string;
}

export interface ModuleReport {
  module: string;
  score: number;
  summary: string;
  status: string;
  metrics: Record<string, any>;
  artifacts: Record<string, string>;
  findings: Array<Omit<Finding, "id" | "created_at">>;
}

export interface RiskReport {
  risk_score: number;
  risk_band: Severity;
  recommendation: string;
  recommendation_label: string;
  narrative: string;
  module_scores: Record<string, number>;
  module_weights: Record<string, number>;
  counts: { critical: number; high: number; total: number };
  contradiction_summary: Array<{
    module: string;
    module_label: string;
    title: string;
    detail: string;
    severity: Severity;
    confidence: number;
  }>;
  modules: Record<string, ModuleReport>;
}

export interface ApplicationSummary {
  id: string;
  reference: string;
  applicant_name: string;
  loan_type: string;
  loan_amount: number;
  declared_income: number;
  status: string;
  risk_score: number;
  risk_band: Severity | null;
  recommendation: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApplicationDetail extends ApplicationSummary {
  applicant_pan: string | null;
  property_address: string | null;
  property_lat: number | null;
  property_lng: number | null;
  report: RiskReport | null;
  documents: DocumentOut[];
  findings: Finding[];
  events: AuditEvent[];
  case: CaseOut | null;
}

export interface DashboardStats {
  total_applications: number;
  analyzing: number;
  auto_cleared: number;
  manual_review: number;
  escalated: number;
  failed: number;
  open_cases: number;
  avg_risk_score: number;
  fraud_prevented_value: number;
  risk_distribution: Record<string, number>;
  total_findings: number;
  high_severity_findings: number;
  pending_analysis: number;
  recent: ApplicationSummary[];
}

export interface PolicyConfig {
  weights: { document: number; financial: number; verification: number; gis: number; intake: number };
  thresholds: { approve: number; review: number; escalate: number };
}

// ── Calls ────────────────────────────────────────────────────────────
export const getDashboard = () => api.get<DashboardStats>("/dashboard").then((r) => r.data);
export const getPolicy = () => api.get<PolicyConfig>("/config").then((r) => r.data);
export const updatePolicy = (payload: PolicyConfig) =>
  api.patch<PolicyConfig>("/config", payload).then((r) => r.data);
export const batchAnalyze = () =>
  api.post<{ queued: number; application_ids: string[] }>("/applications/batch-analyze").then((r) => r.data);
export const listApplications = () =>
  api.get<ApplicationSummary[]>("/applications").then((r) => r.data);
export const getApplication = (id: string) =>
  api.get<ApplicationDetail>(`/applications/${id}`).then((r) => r.data);
export const createApplication = (payload: Record<string, any>) =>
  api.post<ApplicationDetail>("/applications", payload).then((r) => r.data);
export const uploadDocuments = (id: string, files: File[], docTypes: string[]) => {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  if (docTypes.length) form.append("doc_types", docTypes.join(","));
  return api
    .post<ApplicationDetail>(`/applications/${id}/documents`, form, {
      headers: { "Content-Type": "multipart/form-data" },
    })
    .then((r) => r.data);
};
export const analyzeApplication = (id: string) =>
  api.post(`/applications/${id}/analyze`).then((r) => r.data);
export const recordDecision = (id: string, decision: string, note?: string) =>
  api.post<ApplicationDetail>(`/applications/${id}/decision`, { decision, note }).then((r) => r.data);
export const listCases = () => api.get<CaseOut[]>("/cases").then((r) => r.data);
export const updateCase = (id: string, payload: Record<string, any>) =>
  api.patch<CaseOut>(`/cases/${id}`, payload).then((r) => r.data);

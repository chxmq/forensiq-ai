export const inr = (n: number | null | undefined) => {
  if (n == null) return "—";
  if (Math.abs(n) >= 1e7) return `₹${(n / 1e7).toFixed(2)} Cr`;
  if (Math.abs(n) >= 1e5) return `₹${(n / 1e5).toFixed(2)} L`;
  return `₹${n.toLocaleString("en-IN")}`;
};

export const inrFull = (n: number | null | undefined) =>
  n == null ? "—" : `₹${Math.round(n).toLocaleString("en-IN")}`;

export const timeAgo = (iso: string) => {
  const d = new Date(iso).getTime();
  const s = Math.floor((Date.now() - d) / 1000);
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
};

export const fmtDate = (iso: string) =>
  new Date(iso).toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });

export {
  riskColor,
  riskTint,
  statusColor,
  caseStatusColor,
  palette,
  chart,
} from "./theme";

export const initials = (name: string) =>
  name
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase();

export const statusLabel: Record<string, string> = {
  draft: "Draft",
  analyzing: "Analyzing",
  analyzed: "Analyzed",
  auto_cleared: "Auto-Cleared",
  manual_review: "Manual Review",
  escalated: "Escalated",
  approved: "Approved",
  declined: "Declined",
};

export const moduleLabel: Record<string, string> = {
  forensics: "Document Forensics",
  financial: "Financial Integrity",
  verification: "Cross-Source Verification",
  gis: "GIS / Satellite",
  intake: "Document Pack Completeness",
};

import { DOC_TYPE_LABEL } from "./docTypes";

export const titleCase = (s: string) =>
  s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

export { DOC_TYPE_LABEL };

export const docTypeLabel = (id: string) =>
  DOC_TYPE_LABEL[id] || titleCase(id);

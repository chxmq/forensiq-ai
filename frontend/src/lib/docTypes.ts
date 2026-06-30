/** Canara Bank document intake types — mirrors backend ``document_types.py``. */
export const DOC_TYPES: { id: string; label: string }[] = [
  { id: "identity_proof", label: "PAN / Aadhaar / Identity Proof" },
  { id: "salary_slip", label: "Salary Slip / Pay Slip" },
  { id: "form_16", label: "Form 16" },
  { id: "itr", label: "ITR (Income Tax Return)" },
  { id: "bank_statement", label: "Bank Statement" },
  { id: "land_title", label: "Land Title / Sale Deed" },
  { id: "chain_document", label: "Chain of Title Document" },
  { id: "plan_approval", label: "Plan Approval (Building)" },
  { id: "occupancy_certificate", label: "Occupancy Certificate (OC)" },
  { id: "valuation_report", label: "Valuation Report" },
  { id: "sale_deed", label: "Agreement / Sale Deed" },
  { id: "income_certificate", label: "Income Certificate" },
  { id: "other", label: "Other Supporting Document" },
];

export const DOC_TYPE_LABEL: Record<string, string> = Object.fromEntries(
  DOC_TYPES.map((d) => [d.id, d.label]),
);

export function guessDocType(filename: string): string {
  const lower = filename.toLowerCase();
  if (lower.endsWith(".csv") || lower.includes("statement")) return "bank_statement";
  if (lower.includes("pan") || lower.includes("aadhaar") || lower.includes("aadhar")) return "identity_proof";
  if (lower.includes("form16") || lower.includes("form_16")) return "form_16";
  if (lower.includes("itr")) return "itr";
  if (lower.includes("payslip") || lower.includes("pay_slip") || lower.includes("salary")) return "salary_slip";
  if (lower.includes("income")) return "salary_slip";
  if (lower.includes("chain")) return "chain_document";
  if (lower.includes("plan") && lower.includes("approval")) return "plan_approval";
  if (lower.includes("oc") || lower.includes("occupancy")) return "occupancy_certificate";
  if (lower.includes("valuation")) return "valuation_report";
  if (lower.includes("title") || lower.includes("deed")) return "land_title";
  return "other";
}

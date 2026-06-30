"""Document types aligned with Canara Bank underwriting intake."""

CANARA_DOCUMENT_TYPES: list[dict[str, str]] = [
    {"id": "salary_slip", "label": "Salary Slip / Pay Slip"},
    {"id": "form_16", "label": "Form 16"},
    {"id": "itr", "label": "ITR (Income Tax Return)"},
    {"id": "bank_statement", "label": "Bank Statement"},
    {"id": "land_title", "label": "Land Title / Sale Deed"},
    {"id": "chain_document", "label": "Chain of Title Document"},
    {"id": "plan_approval", "label": "Plan Approval (Building)"},
    {"id": "occupancy_certificate", "label": "Occupancy Certificate (OC)"},
    {"id": "valuation_report", "label": "Valuation Report"},
    {"id": "sale_deed", "label": "Agreement / Sale Deed"},
    {"id": "income_certificate", "label": "Income Certificate"},
    {"id": "other", "label": "Other Supporting Document"},
]

DOC_TYPE_IDS = [d["id"] for d in CANARA_DOCUMENT_TYPES]

INCOME_DOC_TYPES = frozenset({
    "salary_slip", "form_16", "itr", "income_certificate",
})

"""Cross-source verification & contradiction engine.

The differentiator of Forensiq AI: instead of judging each document in
isolation, this engine reconciles the *application narrative* (applicant,
declared values, claimed property) and the *fields extracted from uploaded
documents* against independent trusted registries, then surfaces every
contradiction with evidence. It also emits a knowledge graph (nodes + edges)
so the contradictions can be visualised.
"""
from __future__ import annotations

from typing import Any

from app.services.common import Finding, ModuleResult, Severity
from app.services.verification import registry


def _node(graph: dict, node_id: str, label: str, kind: str, **extra) -> None:
    if node_id not in graph["_seen"]:
        graph["nodes"].append({"id": node_id, "label": label, "type": kind, **extra})
        graph["_seen"].add(node_id)


def _edge(graph: dict, src: str, dst: str, label: str, status: str) -> None:
    graph["edges"].append({"source": src, "target": dst, "label": label, "status": status})


def analyze_verification(application: dict, extracted_fields: dict) -> ModuleResult:
    result = ModuleResult(module="verification")
    graph: dict[str, Any] = {"nodes": [], "edges": [], "_seen": set()}

    applicant = application.get("applicant_name", "Applicant")
    declared_pan = application.get("applicant_pan") or extracted_fields.get("pan")
    survey = extracted_fields.get("survey_number")
    doc_owner = extracted_fields.get("owner_name")
    address = application.get("property_address")
    loan_amount = float(application.get("loan_amount") or 0)
    declared_income = float(application.get("declared_income") or 0)

    _node(graph, "applicant", applicant, "applicant")
    _node(graph, "application", f"Loan ₹{loan_amount:,.0f}", "application")
    _edge(graph, "applicant", "application", "applies for", "neutral")

    # ── Identity verification ───────────────────────────────────
    identity = registry.find_identity(declared_pan, applicant)
    result.metrics["identity_matched"] = bool(identity)
    if identity:
        _node(graph, "identity", f"PAN {identity['pan']}", "registry", source="Identity Registry")
        if identity.get("status") == "not_found":
            _edge(graph, "applicant", "identity", "PAN not found", "contradiction")
            result.add(Finding(
                module="verification", code="IDENTITY_NOT_FOUND",
                title="Applicant identity not found in registry",
                detail=f"PAN '{declared_pan}' could not be verified against the identity registry.",
                severity=Severity.high, confidence=0.8,
                evidence={"pan": declared_pan},
            ))
        else:
            sim = registry.name_similarity(applicant, identity.get("name", ""))
            result.metrics["identity_name_similarity"] = round(sim, 2)
            status = "verified" if sim >= 0.8 else "contradiction"
            _edge(graph, "applicant", "identity", f"name match {sim:.0%}", status)
            if sim < 0.8:
                result.add(Finding(
                    module="verification", code="IDENTITY_NAME_MISMATCH",
                    title="Applicant name does not match PAN records",
                    detail=(
                        f"Application name '{applicant}' differs from the registered "
                        f"holder of PAN {identity['pan']} ('{identity['name']}', "
                        f"{sim:.0%} similar)."
                    ),
                    severity=Severity.high, confidence=0.75,
                    evidence={"application_name": applicant, "registry_name": identity["name"]},
                ))
            # Cross-check declared income vs tax-reported income.
            reported = float(identity.get("reported_annual_income") or 0)
            if reported > 0 and declared_income > reported * 1.6:
                result.add(Finding(
                    module="verification", code="INCOME_VS_TAX_MISMATCH",
                    title="Declared income exceeds tax-reported income",
                    detail=(
                        f"Declared income ₹{declared_income:,.0f} is materially higher than "
                        f"the income on record with tax authorities ₹{reported:,.0f}."
                    ),
                    severity=Severity.medium, confidence=0.7,
                    evidence={"declared": declared_income, "tax_reported": reported},
                ))
    else:
        _node(graph, "identity", "PAN unverified", "registry", source="Identity Registry")
        _edge(graph, "applicant", "identity", "no record", "warning")
        result.add(Finding(
            module="verification", code="IDENTITY_UNVERIFIED",
            title="Applicant identity could not be verified",
            detail="No PAN was extracted/provided, so identity could not be reconciled.",
            severity=Severity.low, confidence=0.5, evidence={},
        ))

    # ── Land record verification ────────────────────────────────
    land = registry.find_land_record(survey, address)
    result.metrics["land_record_matched"] = bool(land)
    if land:
        _node(graph, "property", f"Survey {land['survey_number']}", "property", source="Land Registry",
              lat=land.get("lat"), lng=land.get("lng"))
        _edge(graph, "application", "property", "secured against", "neutral")
        _node(graph, "reg_owner", land["owner_name"], "registry", source="Land Registry")

        # Ownership reconciliation: applicant / document owner vs registry owner.
        claim_name = doc_owner or applicant
        owner_sim = registry.name_similarity(claim_name, land["owner_name"])
        result.metrics["owner_similarity"] = round(owner_sim, 2)
        if owner_sim >= 0.8:
            _edge(graph, "applicant", "reg_owner", f"ownership match {owner_sim:.0%}", "verified")
        else:
            _edge(graph, "applicant", "reg_owner", f"owner mismatch {owner_sim:.0%}", "contradiction")
            result.add(Finding(
                module="verification", code="OWNERSHIP_MISMATCH",
                title="Property owner does not match the applicant",
                detail=(
                    f"Land registry lists the owner of survey {land['survey_number']} as "
                    f"'{land['owner_name']}', which does not match the applicant/document "
                    f"name '{claim_name}' ({owner_sim:.0%} similar). The applicant may not "
                    "hold clear title to the collateral."
                ),
                severity=Severity.critical, confidence=0.8,
                evidence={"registry_owner": land["owner_name"], "claimed_owner": claim_name},
            ))

        # Encumbrance / non-transferable / litigation.
        enc = land.get("encumbrance", "none")
        if enc == "mortgage_active":
            result.add(Finding(
                module="verification", code="EXISTING_ENCUMBRANCE",
                title="Collateral already carries an active mortgage",
                detail=land.get("encumbrance_detail", "An active mortgage is registered against this property."),
                severity=Severity.high, confidence=0.85, evidence={"encumbrance": enc},
            ))
            _edge(graph, "property", "reg_owner", "active mortgage", "contradiction")
        elif enc in ("non_transferable",):
            result.add(Finding(
                module="verification", code="NON_TRANSFERABLE",
                title="Property is legally non-transferable",
                detail=(
                    f"Survey {land['survey_number']} is classified as "
                    f"'{land.get('land_use')}' and cannot be pledged or transferred."
                ),
                severity=Severity.critical, confidence=0.9, evidence={"land_use": land.get("land_use")},
            ))
        if land.get("litigation"):
            result.add(Finding(
                module="verification", code="ACTIVE_LITIGATION",
                title="Property is under active litigation",
                detail=land["litigation"],
                severity=Severity.high, confidence=0.8, evidence={"case": land["litigation"]},
            ))

        # Declared value vs registered value.
        max_amount = extracted_fields.get("max_amount") or loan_amount
        reg_value = float(land.get("registered_value") or 0)
        if reg_value > 0 and max_amount and max_amount > reg_value * 1.6:
            result.add(Finding(
                module="verification", code="VALUE_INFLATION",
                title="Declared property value far exceeds registered value",
                detail=(
                    f"Document/loan value (₹{max_amount:,.0f}) is significantly higher than "
                    f"the registered value (₹{reg_value:,.0f}) — possible over-valuation to "
                    "secure a larger loan."
                ),
                severity=Severity.medium, confidence=0.65,
                evidence={"declared_value": max_amount, "registered_value": reg_value},
            ))

        # Area mismatch.
        doc_area = extracted_fields.get("area_value")
        if doc_area and land.get("area_value"):
            if abs(doc_area - land["area_value"]) / max(land["area_value"], 1) > 0.25 and \
               (extracted_fields.get("area_unit") or "").startswith(str(land.get("area_unit", ""))[:2]):
                result.add(Finding(
                    module="verification", code="AREA_MISMATCH",
                    title="Property area differs from registry",
                    detail=(
                        f"Document states {doc_area} {extracted_fields.get('area_unit')} but "
                        f"registry records {land['area_value']} {land['area_unit']}."
                    ),
                    severity=Severity.medium, confidence=0.6,
                    evidence={"document_area": doc_area, "registry_area": land["area_value"]},
                ))
    else:
        _node(graph, "property", "Property unverified", "property")
        _edge(graph, "application", "property", "no registry match", "warning")
        result.add(Finding(
            module="verification", code="LAND_RECORD_NOT_FOUND",
            title="Property could not be located in land registry",
            detail=(
                "No matching land record was found for the provided survey number / "
                "address. Ownership and title could not be independently confirmed."
            ),
            severity=Severity.medium, confidence=0.55,
            evidence={"survey_number": survey, "address": address},
        ))

    graph.pop("_seen", None)
    result.artifacts = {}
    result.metrics["knowledge_graph"] = graph
    result.compute_score()
    result.summary = (
        f"{len(result.findings)} cross-source contradiction(s) detected across "
        "identity, ownership and registry sources." if result.findings
        else "All cross-source checks reconciled successfully."
    )
    return result

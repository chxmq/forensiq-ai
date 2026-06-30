import { useCallback, useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  ArrowLeft,
  ShieldCheck,
  ShieldAlert,
  FileText,
  ScanSearch,
  Network,
  Satellite,
  History,
  Cpu,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  MapPin,
} from "lucide-react";
import {
  getApplication,
  analyzeApplication,
  recordDecision,
  type ApplicationDetail as AppDetail,
  type Severity,
} from "../lib/api";
import { inrFull, inr, fmtDate, riskColor, riskTint, moduleLabel, titleCase, statusLabel, docTypeLabel } from "../lib/format";
import { RiskBadge, ScoreRing, SeverityDot, StatusPill, Spinner } from "../components/common";
import { openStream } from "../lib/ws";
import { artifactUrl } from "../lib/auth";
import BenfordChart from "../components/BenfordChart";
import KnowledgeGraph from "../components/KnowledgeGraph";
import PropertyMap from "../components/PropertyMap";

const TABS = [
  { id: "overview", label: "Executive Summary", icon: ShieldCheck },
  { id: "forensics", label: "Document Analysis", icon: ScanSearch },
  { id: "financial", label: "Financial Analysis", icon: FileText },
  { id: "verification", label: "Cross-Source", icon: Network },
  { id: "gis", label: "Property / Location", icon: Satellite },
  { id: "audit", label: "Audit Trail", icon: History },
];

export default function ApplicationDetail() {
  const { id } = useParams();
  const [app, setApp] = useState<AppDetail | null>(null);
  const [tab, setTab] = useState("overview");
  const [analyzing, setAnalyzing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  const load = useCallback(() => {
    if (id) getApplication(id).then(setApp).catch(() => {});
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const runAnalysis = () => {
    if (!id) return;
    setAnalyzing(true);
    setProgress(0);
    setAnalysisError(null);
    const ws = openStream(`/ws/applications/${id}`, (e) => {
      if (e.type === "stage") setProgress(e.progress || 0);
      if (e.type === "error") {
        setAnalysisError(e.message || "Analysis failed.");
        ws.close();
        setAnalyzing(false);
        load();
      }
      if (e.type === "completed") {
        setProgress(100);
        setTimeout(() => {
          ws.close();
          setAnalyzing(false);
          load();
        }, 600);
      }
    });
    setTimeout(() => analyzeApplication(id), 400);
  };

  const decide = async (decision: string) => {
    if (!id) return;
    await recordDecision(id, decision);
    load();
  };

  if (!app)
    return (
      <div className="grid h-[60vh] place-items-center">
        <Spinner label="Loading report…" />
      </div>
    );

  const report = app.report;
  const ms = report?.module_scores || {};
  const band = app.risk_band || "low";

  return (
    <div className="space-y-5">
      <Link to="/applications" className="inline-flex items-center gap-2 text-sm text-muted hover:text-brand-500">
        <ArrowLeft className="h-4 w-4" /> Back to applications
      </Link>

      {/* Header */}
      <div className="card relative overflow-hidden p-5">
        {report && <span className="absolute left-0 top-0 h-full w-1" style={{ background: riskColor[band] }} />}
        <div className="flex flex-wrap items-center gap-5">
          {report ? (
            <ScoreRing score={app.risk_score} size={92} />
          ) : (
            <div className="grid h-[92px] w-[92px] place-items-center rounded-full border border-dashed border-line text-center text-[11px] text-faint">
              Not analyzed
            </div>
          )}

          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2.5">
              {app.risk_band && <RiskBadge band={app.risk_band} />}
              <h1 className="text-xl font-extrabold tracking-tight text-ink">{app.applicant_name}</h1>
              <StatusPill status={app.status} />
            </div>
            <p className="mt-1 font-mono text-xs text-faint">
              {app.reference} · PAN {app.applicant_pan || "—"} · {titleCase(app.loan_type)}
            </p>
            {report && (
              <p className="mt-2 text-sm">
                <span className="text-muted">Recommendation: </span>
                <span className="font-bold" style={{ color: riskColor[band] }}>
                  {report.recommendation_label}
                </span>
              </p>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button className="btn-secondary" onClick={runAnalysis} disabled={analyzing}>
              <Cpu className="h-4 w-4" /> {report ? "Re-run" : "Run analysis"}
            </button>
            {report && (
              <>
                <button className="btn-secondary" onClick={() => decide("declined")}>
                  <XCircle className="h-4 w-4" /> Decline
                </button>
                <button className="btn-secondary" onClick={() => decide("manual_review")}>
                  <AlertTriangle className="h-4 w-4" /> Review
                </button>
                <button className="btn-primary" onClick={() => decide("approved")}>
                  <CheckCircle2 className="h-4 w-4" /> Approve
                </button>
              </>
            )}
          </div>
        </div>

        {analyzing && (
          <div className="mt-4">
            <div className="h-2 overflow-hidden rounded-full bg-line-soft">
              <div className="h-full bg-brand-500 transition-all" style={{ width: `${progress}%` }} />
            </div>
            <p className="mt-1 text-xs text-muted">Analyzing… {progress}%</p>
          </div>
        )}
        {analysisError && (
          <div className="mt-4 rounded-lg border border-risk-critical/30 bg-risk-critical/5 px-4 py-3 text-sm text-risk-critical">
            Analysis failed: {analysisError}
          </div>
        )}
      </div>

      {/* Fact strip */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Fact label="Applicant" value={app.applicant_name} sub={app.applicant_pan ? `PAN ${app.applicant_pan}` : "Identity on file"} />
        <Fact label="Loan Type" value={titleCase(app.loan_type)} sub={statusLabel[app.status]} />
        <Fact label="Requested Amount" value={inrFull(app.loan_amount)} sub={`Declared income ${inr(app.declared_income)}`} />
        <Fact
          label="Findings"
          value={String(app.findings.length)}
          sub={`${app.documents.length} documents analyzed`}
        />
      </div>

      {app.case && (
        <Link to="/cases" className="flex items-center gap-2 rounded-xl border border-risk-critical/30 bg-risk-critical/5 px-4 py-3 text-sm">
          <ShieldAlert className="h-4 w-4 text-risk-critical" />
          <span className="font-semibold text-risk-critical">{app.case.case_number}</span>
          <span className="text-muted">— escalated to Fraud Investigation Unit</span>
        </Link>
      )}

      {!report && !analyzing && (
        <div className="card card-pad text-center text-muted">
          This application has not been analyzed yet. Click <b className="text-ink">Run analysis</b> to execute the integrity pipeline.
        </div>
      )}

      {report && (
        <>
          <div className="flex gap-1 overflow-x-auto border-b border-line">
            {TABS.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`flex items-center gap-2 whitespace-nowrap border-b-2 px-3.5 py-3 text-sm font-semibold transition ${
                  tab === t.id ? "border-navy-900 text-ink" : "border-transparent text-faint hover:text-muted"
                }`}
              >
                <t.icon className="h-4 w-4" /> {t.label}
              </button>
            ))}
          </div>

          {tab === "overview" && <Overview app={app} />}
          {tab === "forensics" && <Forensics app={app} />}
          {tab === "financial" && <Financial app={app} />}
          {tab === "verification" && <Verification app={app} />}
          {tab === "gis" && <Gis app={app} />}
          {tab === "audit" && <Audit app={app} />}
        </>
      )}
    </div>
  );

  function Overview({ app }: { app: AppDetail }) {
    const r = app.report!;
    const graph = r.modules?.verification?.metrics?.knowledge_graph;

    return (
      <div className="space-y-6">
        {graph && (
          <div className="card card-pad">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div>
                <h3 className="text-lg font-bold text-ink">Entity Consistency Map</h3>
                <p className="text-sm text-muted">
                  Applicant, property, and registry data — red links are contradictions that manual review often misses.
                </p>
              </div>
              {r.contradiction_summary.length > 0 && (
                <span className="chip" style={{ color: riskColor.critical, background: riskTint.critical }}>
                  {r.contradiction_summary.length} contradiction(s)
                </span>
              )}
            </div>
            <KnowledgeGraph graph={graph} />
          </div>
        )}

        <div className="grid gap-6 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-2">
            <div className="card card-pad">
              <h3 className="mb-2 font-semibold text-ink">Risk Narrative</h3>
              <p className="text-sm leading-relaxed text-muted">{r.narrative}</p>

              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {Object.entries(ms).map(([k, v]) => {
                  const b = v >= 75 ? "critical" : v >= 60 ? "high" : v >= 30 ? "medium" : "low";
                  return (
                    <div key={k} className="rounded-lg border border-line p-3" style={{ borderLeft: `3px solid ${riskColor[b]}` }}>
                      <p className="text-label-caps uppercase" style={{ color: riskColor[b] }}>
                        {moduleLabel[k] || k}
                      </p>
                      <p className="mt-1 font-mono text-xl font-extrabold text-ink">
                        {v.toFixed(0)}
                        <span className="text-sm font-medium text-faint">/100</span>
                      </p>
                      <p className="text-[11px] text-faint">weight {Math.round((r.module_weights[k] || 0) * 100)}%</p>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="card card-pad">
              <h3 className="mb-3 text-sm font-semibold text-ink">Module Risk Breakdown</h3>
              <div className="space-y-3">
                {Object.entries(ms).map(([k, v]) => {
                  const b = v >= 75 ? "critical" : v >= 60 ? "high" : v >= 30 ? "medium" : "low";
                  return (
                    <div key={k}>
                      <div className="mb-1 flex items-center justify-between text-xs">
                        <span className="font-medium text-muted">{moduleLabel[k] || k}</span>
                        <span className="font-mono font-semibold" style={{ color: riskColor[b] }}>
                          {v.toFixed(0)}
                        </span>
                      </div>
                      <div className="h-2 overflow-hidden rounded-full bg-line-soft">
                        <div className="h-full rounded-full transition-all" style={{ width: `${v}%`, background: riskColor[b] }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          <div className="card card-pad">
            <h3 className="mb-3 text-sm font-semibold text-ink">
              Cross-Source Contradictions <span className="text-faint">({r.contradiction_summary.length})</span>
            </h3>
            {r.contradiction_summary.length === 0 ? (
              <p className="text-sm text-muted">No high-severity contradictions found.</p>
            ) : (
              <div className="space-y-2">
                {r.contradiction_summary.map((c, i) => (
                  <div key={i} className="rounded-lg border border-line bg-canvas p-3" style={{ borderLeft: `3px solid ${riskColor[c.severity]}` }}>
                    <div className="flex items-center gap-2">
                      <SeverityDot severity={c.severity} />
                      <span className="text-sm font-semibold text-ink">{c.title}</span>
                    </div>
                    <p className="mt-1 text-xs text-muted">{c.detail}</p>
                    <p className="mt-1 text-label-caps uppercase text-faint">
                      {c.module_label} · {(c.confidence * 100).toFixed(0)}% confidence
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  function Forensics({ app }: { app: AppDetail }) {
    return (
      <div className="space-y-4">
        {app.documents.map((d) => {
          const artifacts = d.artifacts || {};
          const docFindings = (d.forensics?.findings || []) as any[];
          const b = d.integrity_score >= 60 ? "critical" : d.integrity_score >= 30 ? "medium" : "low";
          return (
            <div key={d.id} className="card card-pad">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="grid h-10 w-10 place-items-center rounded-lg bg-canvas">
                    <FileText className="h-5 w-5 text-brand-500" />
                  </div>
                  <div>
                    <p className="font-semibold text-ink">{d.filename}</p>
                    <p className="font-mono text-[11px] text-faint">
                      {docTypeLabel(d.doc_type)} · {(d.size_bytes / 1024).toFixed(0)} KB · SHA {d.sha256?.slice(0, 10)}
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-label-caps uppercase text-faint">Integrity Risk</p>
                  <p className="font-mono text-lg font-extrabold" style={{ color: riskColor[b] }}>
                    {d.integrity_score.toFixed(0)}
                  </p>
                </div>
              </div>

              {Object.keys(artifacts).length > 0 && (
                <div className="mt-4 grid gap-3 sm:grid-cols-3">
                  {Object.entries(artifacts).map(([k, url]) => (
                    <figure key={k} className="overflow-hidden rounded-lg border border-line bg-canvas">
                      <img src={artifactUrl(url as string)} alt={k} className="h-40 w-full object-cover" />
                      <figcaption className="px-2 py-1.5 text-label-caps uppercase text-faint">{k.replace(/_/g, " ")}</figcaption>
                    </figure>
                  ))}
                </div>
              )}

              {docFindings.length > 0 ? (
                <div className="mt-4 space-y-2">
                  {docFindings.map((f: any, i: number) => (
                    <FindingRow key={i} f={f} />
                  ))}
                </div>
              ) : (
                <p className="mt-4 text-sm text-muted">No tampering signatures detected in this document.</p>
              )}

              {d.extracted_fields && Object.keys(d.extracted_fields).length > 0 && (
                <div className="mt-4 rounded-lg border border-line bg-canvas p-3">
                  <p className="label mb-2">Extracted Fields</p>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(d.extracted_fields)
                      .filter(([k]) => !["text_length"].includes(k))
                      .map(([k, v]) => (
                        <span key={k} className="chip border border-line bg-surface text-muted">
                          <span className="text-faint">{k}:</span> {String(Array.isArray(v) ? v.join(", ") : v).slice(0, 40)}
                        </span>
                      ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    );
  }

  function Financial({ app }: { app: AppDetail }) {
    const m = app.report!.modules.financial;
    const metrics = m.metrics || {};
    const findings = m.findings || [];
    return (
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card card-pad">
          <h3 className="mb-1 text-sm font-semibold text-ink">Benford's Law — First-Digit Distribution</h3>
          <p className="mb-3 text-xs text-muted">
            {metrics.benford_applicable
              ? `χ² = ${metrics.benford_chi2} (critical 15.51). Deviation indicates fabricated figures.`
              : "Insufficient monetary values for Benford analysis."}
          </p>
          {metrics.benford_observed ? (
            <BenfordChart observed={metrics.benford_observed} expected={metrics.benford_expected} />
          ) : (
            <p className="text-sm text-muted">No statement data.</p>
          )}
        </div>

        <div className="card card-pad space-y-3">
          <h3 className="text-sm font-semibold text-ink">Financial Integrity Metrics</h3>
          <div className="grid grid-cols-2 gap-3">
            <KV label="Transactions" v={metrics.transaction_count} />
            <KV label="Anomaly Rate" v={metrics.iforest_anomaly_ratio != null ? `${(metrics.iforest_anomaly_ratio * 100).toFixed(0)}%` : "—"} />
            <KV label="Observed Inflow" v={metrics.observed_annual_inflow ? inr(metrics.observed_annual_inflow) : "—"} />
            <KV label="Declared Income" v={metrics.declared_income ? inr(metrics.declared_income) : "—"} />
            <KV label="Income Overstatement" v={metrics.income_to_inflow_ratio ? `${metrics.income_to_inflow_ratio}×` : "—"} highlight={metrics.income_to_inflow_ratio > 1.5} />
            <KV label="Round-Number Ratio" v={metrics.round_amount_ratio != null ? `${(metrics.round_amount_ratio * 100).toFixed(0)}%` : "—"} />
          </div>
          {metrics.payslip_check_applicable && (
            <div className="rounded-lg border border-line bg-canvas p-3">
              <p className="label mb-2">Payslip vs Bank Statement</p>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <KV label="Document Income" v={metrics.payslip_gross_annual ? inr(metrics.payslip_gross_annual) : "—"} />
                <KV label="Bank Credits (annualized)" v={metrics.annualized_bank_credits ? inr(metrics.annualized_bank_credits) : "—"} />
                <KV label="Match Ratio" v={metrics.payslip_to_bank_ratio != null ? `${(metrics.payslip_to_bank_ratio * 100).toFixed(0)}%` : "—"} highlight={metrics.payslip_to_bank_ratio != null && metrics.payslip_to_bank_ratio < 0.45} />
                <KV label="Source Doc" v={metrics.payslip_source_document || "—"} />
              </div>
            </div>
          )}
          {metrics.iforest_examples?.length > 0 && (
            <div>
              <p className="label mb-1.5">Top Anomalous Transactions</p>
              <div className="space-y-1">
                {metrics.iforest_examples.slice(0, 4).map((t: any, i: number) => (
                  <div key={i} className="flex justify-between rounded-lg bg-canvas px-3 py-1.5 text-xs">
                    <span className="text-muted">{t.date} · {t.description || "—"}</span>
                    <span className="font-mono font-semibold text-risk-high">{inr(t.amount)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="card card-pad lg:col-span-2">
          <h3 className="mb-3 text-sm font-semibold text-ink">Findings</h3>
          {findings.length ? (
            <div className="space-y-2">{findings.map((f: any, i: number) => <FindingRow key={i} f={f} />)}</div>
          ) : (
            <p className="text-sm text-muted">{m.summary}</p>
          )}
        </div>
      </div>
    );
  }

  function Verification({ app }: { app: AppDetail }) {
    const m = app.report!.modules.verification;
    const graph = m.metrics?.knowledge_graph;
    const findings = m.findings || [];
    return (
      <div className="grid gap-6">
        <div className="card card-pad">
          <h3 className="mb-1 text-sm font-semibold text-ink">Entity Consistency Map</h3>
          <p className="mb-2 text-xs text-muted">
            Applicant, application, property and trusted registries — red links are contradictions.
          </p>
          {graph ? <KnowledgeGraph graph={graph} /> : <p className="text-sm text-muted">No graph available.</p>}
        </div>
        <div className="card card-pad">
          <h3 className="mb-3 text-sm font-semibold text-ink">Cross-Source Findings</h3>
          {findings.length ? (
            <div className="space-y-2">{findings.map((f: any, i: number) => <FindingRow key={i} f={f} />)}</div>
          ) : (
            <p className="text-sm text-muted">{m.summary}</p>
          )}
        </div>
      </div>
    );
  }

  function Gis({ app }: { app: AppDetail }) {
    const m = app.report!.modules.gis;
    const metrics = m.metrics || {};
    const map = metrics.map;
    const geocode = metrics.geocode as { source_label?: string } | undefined;
    const findings = m.findings || [];
    const mismatch = metrics.claimed_use !== metrics.observed_use;
    return (
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card card-pad">
          <h3 className="mb-3 text-sm font-semibold text-ink">Satellite Land-Use View</h3>
          {map?.lat ? (
            <PropertyMap metrics={metrics} />
          ) : (
            <p className="text-sm text-muted">
              Parcel location not yet resolved. Enter the property address on the application or upload a land title
              with survey/plot number — coordinates are derived automatically.
            </p>
          )}
          {geocode?.source_label && (
            <p className="mt-2 text-xs text-muted">Location: {geocode.source_label}</p>
          )}
          {app.property_address && (
            <p className="mt-3 flex items-center gap-1.5 text-xs text-muted">
              <MapPin className="h-3.5 w-3.5" /> {app.property_address}
            </p>
          )}
        </div>
        <div className="card card-pad space-y-3">
          <h3 className="text-sm font-semibold text-ink">Remote-Sensing Analysis</h3>
          <div className="flex gap-2">
            <span className="chip border border-line bg-surface text-muted">Claimed: {metrics.claimed_use ? titleCase(metrics.claimed_use) : "—"}</span>
            <span
              className="chip"
              style={mismatch ? { color: riskColor.critical, background: riskTint.critical } : { color: riskColor.low, background: riskTint.low }}
            >
              Observed: {metrics.observed_use ? titleCase(metrics.observed_use) : "—"}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <KV label="Built-up Ratio" v={metrics.built_up_ratio != null ? `${(metrics.built_up_ratio * 100).toFixed(0)}%` : "—"} />
            <KV label="Vegetation (NDVI)" v={metrics.ndvi ?? "—"} />
            <KV label="Structures" v={metrics.structures_detected ?? "—"} />
            <KV label="Change Detection" v={metrics.change_since_prior ? titleCase(metrics.change_since_prior) : "—"} />
          </div>
          {metrics.imagery_date && <p className="text-xs text-faint">Imagery date: {metrics.imagery_date}</p>}
          {findings.length > 0 && (
            <div className="space-y-2 pt-2">{findings.map((f: any, i: number) => <FindingRow key={i} f={f} />)}</div>
          )}
        </div>
      </div>
    );
  }

  function Audit({ app }: { app: AppDetail }) {
    return (
      <div className="card card-pad">
        <h3 className="mb-4 text-sm font-semibold text-ink">Detailed Activity & Log</h3>
        <div className="space-y-0">
          {[...app.events].reverse().map((e, i, arr) => (
            <div key={e.id} className="flex gap-3">
              <div className="flex flex-col items-center">
                <div className="mt-1.5 h-2.5 w-2.5 rounded-full bg-brand-500" />
                {i < arr.length - 1 && <div className="w-px flex-1 bg-line" />}
              </div>
              <div className="pb-5">
                <p className="text-sm font-semibold text-ink">{titleCase(e.action)}</p>
                {e.detail && <p className="text-xs text-muted">{e.detail}</p>}
                <p className="mt-0.5 font-mono text-[11px] text-faint">
                  {e.actor} · {fmtDate(e.created_at)}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }
}

function Fact({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="card p-4">
      <p className="label">{label}</p>
      <p className="mt-1 truncate text-lg font-bold text-ink">{value}</p>
      {sub && <p className="mt-0.5 truncate text-xs text-faint">{sub}</p>}
    </div>
  );
}

function FindingRow({ f }: { f: { title: string; detail: string; severity: Severity; confidence: number; code?: string } }) {
  return (
    <div className="rounded-lg border border-line bg-canvas p-3" style={{ borderLeft: `3px solid ${riskColor[f.severity]}` }}>
      <div className="flex items-center gap-2">
        <SeverityDot severity={f.severity} />
        <span className="text-sm font-semibold text-ink">{f.title}</span>
        <span className="ml-auto font-mono text-[10px] text-faint">{f.code}</span>
      </div>
      <p className="mt-1 text-xs leading-relaxed text-muted">{f.detail}</p>
      <div className="mt-1.5 flex items-center gap-2">
        <div className="h-1 w-24 overflow-hidden rounded-full bg-line-soft">
          <div className="h-full rounded-full" style={{ width: `${f.confidence * 100}%`, background: riskColor[f.severity] }} />
        </div>
        <span className="text-[10px] text-faint">{(f.confidence * 100).toFixed(0)}% confidence</span>
      </div>
    </div>
  );
}

function KV({ label, v, highlight }: { label: string; v: any; highlight?: boolean }) {
  return (
    <div className="rounded-lg bg-canvas p-2.5">
      <p className="label">{label}</p>
      <p className={`text-sm font-semibold ${highlight ? "text-risk-critical" : "text-ink"}`}>{v ?? "—"}</p>
    </div>
  );
}

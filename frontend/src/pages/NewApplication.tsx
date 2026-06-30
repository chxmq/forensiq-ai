import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { UploadCloud, FileText, X, Cpu, CheckCircle2, ArrowRight, Activity } from "lucide-react";
import {
  createApplication,
  uploadDocuments,
  analyzeApplication,
  type ApplicationDetail,
} from "../lib/api";
import { openStream, type PipelineEvent } from "../lib/ws";
import { riskColor, titleCase, inr } from "../lib/format";
import { DOC_TYPES, guessDocType } from "../lib/docTypes";

type Stage = { key: string; label: string };

export default function NewApplication() {
  const navigate = useNavigate();
  const fileRef = useRef<HTMLInputElement>(null);
  const [step, setStep] = useState(1);
  const [app, setApp] = useState<ApplicationDetail | null>(null);
  const [busy, setBusy] = useState(false);

  const [form, setForm] = useState({
    applicant_name: "",
    applicant_pan: "",
    loan_type: "home_loan",
    loan_amount: 5000000,
    declared_income: 1500000,
    property_address: "",
  });
  const [files, setFiles] = useState<{ file: File; type: string }[]>([]);

  const [stages, setStages] = useState<Stage[]>([]);
  const [progress, setProgress] = useState(0);
  const [currentStage, setCurrentStage] = useState("");
  const [liveFindings, setLiveFindings] = useState<PipelineEvent[]>([]);
  const [done, setDone] = useState<PipelineEvent | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  const set = (k: string, v: any) => setForm((f) => ({ ...f, [k]: v }));

  const submitForm = async () => {
    setBusy(true);
    try {
      const created = await createApplication(form);
      setApp(created);
      setStep(2);
    } finally {
      setBusy(false);
    }
  };

  const onPick = (list: FileList | null) => {
    if (!list) return;
    const next = Array.from(list).map((file) => {
      const lower = file.name.toLowerCase();
      return { file, type: guessDocType(lower) };
    });
    setFiles((f) => [...f, ...next]);
  };

  const doUpload = async () => {
    if (!app) return;
    setBusy(true);
    try {
      await uploadDocuments(app.id, files.map((f) => f.file), files.map((f) => f.type));
      setStep(3);
    } finally {
      setBusy(false);
    }
  };

  const runAnalysis = async () => {
    if (!app) return;
    setStep(4);
    setProgress(0);
    setLiveFindings([]);
    setDone(null);
    setAnalysisError(null);
    const ws = openStream(`/ws/applications/${app.id}`, (e) => {
      if (e.type === "started") setStages(e.stages || []);
      if (e.type === "stage") {
        setProgress(e.progress || 0);
        setCurrentStage(e.label || "");
      }
      if (e.type === "finding") setLiveFindings((f) => [e, ...f]);
      if (e.type === "error") {
        setAnalysisError(e.message || "Analysis failed.");
        ws.close();
      }
      if (e.type === "completed") {
        setProgress(100);
        setDone(e);
        setTimeout(() => ws.close(), 500);
      }
    });
    setTimeout(() => analyzeApplication(app.id), 400);
  };

  const steps = ["Details", "Documents", "Review", "Analysis"];

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-3xl font-extrabold tracking-tight text-ink">New Underwriting Analysis</h1>
        <p className="mt-1 text-sm text-muted">
          Create an application, attach documents and run the integrity pipeline in real time.
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="space-y-6">
          <Steps steps={steps} step={step} />

          {step === 1 && (
            <div className="card card-pad space-y-5">
              <SectionTitle title="Primary Identification" sub="Verify entity details and requested loan parameters." />
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Applicant Name">
                  <input className="input" value={form.applicant_name} onChange={(e) => set("applicant_name", e.target.value)} placeholder="e.g. Ramesh Kumar Sharma" />
                </Field>
                <Field label="PAN">
                  <input className="input uppercase" value={form.applicant_pan} onChange={(e) => set("applicant_pan", e.target.value.toUpperCase())} placeholder="ABCPS1234K" />
                </Field>
                <Field label="Loan Type">
                  <select className="input" value={form.loan_type} onChange={(e) => set("loan_type", e.target.value)}>
                    {["home_loan", "business_loan", "loan_against_property", "agri_loan"].map((t) => (
                      <option key={t} value={t}>{titleCase(t)}</option>
                    ))}
                  </select>
                </Field>
                <Field label="Loan Amount (₹)">
                  <input type="number" className="input" value={form.loan_amount} onChange={(e) => set("loan_amount", Number(e.target.value))} />
                </Field>
                <Field label="Declared Annual Income (₹)">
                  <input type="number" className="input" value={form.declared_income} onChange={(e) => set("declared_income", Number(e.target.value))} />
                </Field>
                <Field label="Property Address">
                  <input
                    className="input sm:col-span-2"
                    value={form.property_address}
                    onChange={(e) => set("property_address", e.target.value)}
                    placeholder="Plot 142/3, Whitefield, Bengaluru, Karnataka 560066"
                  />
                  <p className="mt-1.5 text-xs text-muted">
                    Location is resolved automatically from the address and land title documents — no GPS entry needed.
                  </p>
                </Field>
              </div>
              <div className="flex justify-end border-t border-line pt-4">
                <button className="btn-primary" disabled={!form.applicant_name || busy} onClick={submitForm}>
                  Next Step <ArrowRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}

          {step === 2 && app && (
            <div className="card card-pad space-y-4">
              <SectionTitle title="Document Intake" sub="Attach the documents this application should be assessed against." />
              <div
                onClick={() => fileRef.current?.click()}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  onPick(e.dataTransfer.files);
                }}
                className="grid cursor-pointer place-items-center rounded-xl border-2 border-dashed border-line bg-canvas py-12 transition hover:border-brand-500/50 hover:bg-brand-50"
              >
                <UploadCloud className="h-10 w-10 text-brand-500" />
                <p className="mt-2 text-sm font-semibold text-ink">Drop documents here or click to browse</p>
                <p className="text-xs text-faint">Land titles, income certificates, bank statements (CSV), valuation reports</p>
                <input ref={fileRef} type="file" multiple hidden onChange={(e) => onPick(e.target.files)} />
              </div>

              {files.length > 0 && (
                <div className="space-y-2">
                  {files.map((f, i) => (
                    <div key={i} className="flex items-center gap-3 rounded-lg border border-line bg-canvas p-3">
                      <FileText className="h-5 w-5 text-brand-500" />
                      <span className="flex-1 truncate text-sm font-medium text-ink">{f.file.name}</span>
                      <select
                        className="rounded-lg border border-line bg-surface px-2 py-1 text-xs text-muted"
                        value={f.type}
                        onChange={(e) => setFiles((arr) => arr.map((x, j) => (j === i ? { ...x, type: e.target.value } : x)))}
                      >
                    {DOC_TYPES.map((t) => (
                      <option key={t.id} value={t.id}>{t.label}</option>
                    ))}
                      </select>
                      <button onClick={() => setFiles((arr) => arr.filter((_, j) => j !== i))}>
                        <X className="h-4 w-4 text-faint hover:text-risk-critical" />
                      </button>
                    </div>
                  ))}
                </div>
              )}

              <div className="flex justify-between border-t border-line pt-4">
                <button className="btn-ghost" onClick={() => setStep(1)}>Back</button>
                <button className="btn-primary" disabled={files.length === 0 || busy} onClick={doUpload}>
                  Upload {files.length > 0 ? `${files.length} file(s)` : ""} <ArrowRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}

          {step === 3 && app && (
            <div className="card card-pad space-y-5 text-center">
              <div className="mx-auto grid h-16 w-16 place-items-center rounded-2xl bg-brand-50">
                <Cpu className="h-8 w-8 text-brand-500" />
              </div>
              <div>
                <p className="text-lg font-bold text-ink">Ready to analyze</p>
                <p className="mt-1 text-sm text-muted">
                  {app.applicant_name} · {files.length} document(s) attached. The pipeline runs forensics,
                  financial, cross-source and GIS checks.
                </p>
              </div>
              <button className="btn-primary mx-auto" onClick={runAnalysis}>
                <Cpu className="h-4 w-4" /> Run Forensiq Analysis
              </button>
            </div>
          )}

          {step === 4 && app && (
            <div className="space-y-4">
              <div className="card card-pad">
                <div className="mb-3 flex items-center justify-between">
                  <h2 className="font-semibold text-ink">{done ? "Analysis complete" : "Analyzing…"}</h2>
                  <span className="font-mono text-sm font-bold text-brand-500">{progress}%</span>
                </div>
                <div className="h-2.5 overflow-hidden rounded-full bg-line-soft">
                  <div className="h-full rounded-full bg-brand-500 transition-all duration-500" style={{ width: `${progress}%` }} />
                </div>
                <p className="mt-2 text-xs text-muted">{done ? "Pipeline finished." : currentStage}</p>
                {analysisError && (
                  <p className="mt-2 text-sm text-risk-critical">Analysis failed: {analysisError}</p>
                )}

                {stages.length > 0 && (
                  <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
                    {stages.map((s, i) => {
                      const reached = progress >= ((i + 1) / stages.length) * 100 - 1;
                      return (
                        <div
                          key={s.key}
                          className={`rounded-lg border p-2 text-center text-[11px] font-medium transition ${
                            reached ? "border-brand-500/30 bg-brand-50 text-brand-600" : "border-line text-faint"
                          }`}
                        >
                          {s.label}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {done && (
                <div className="card card-pad flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <CheckCircle2 className="h-6 w-6" style={{ color: riskColor[String(done.risk_band)] }} />
                    <div>
                      <p className="font-semibold text-ink">
                        Risk {done.risk_score?.toFixed?.(0)} / 100 · {String(done.risk_band).toUpperCase()}
                      </p>
                      <p className="text-xs text-muted">{done.recommendation_label}</p>
                    </div>
                  </div>
                  <button className="btn-primary" onClick={() => navigate(`/applications/${app.id}`)}>
                    View full report <ArrowRight className="h-4 w-4" />
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Live analysis side panel */}
        <aside className="space-y-4">
          <div className="card card-pad">
            <p className="flex items-center gap-2 text-label-caps uppercase text-faint">
              <Activity className="h-4 w-4 text-brand-500" /> Live Analysis
            </p>
            {step < 4 ? (
              <p className="mt-3 text-sm text-muted">Waiting for documents to begin deep scanning…</p>
            ) : (
              <div className="mt-3 space-y-1.5">
                {liveFindings.length === 0 && !done && (
                  <p className="text-sm text-muted">Scanning documents and cross-checking sources…</p>
                )}
                {liveFindings.map((f, i) => (
                  <div key={i} className="flex items-start gap-2 rounded-lg bg-canvas px-3 py-2 text-sm">
                    <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full" style={{ background: riskColor[f.severity] || riskColor.high }} />
                    <div>
                      <p className="text-ink">{f.title}</p>
                      <p className="text-xs text-faint">{titleCase(f.module || "")}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {app && (
            <div className="card card-pad">
              <p className="text-label-caps uppercase text-faint">Application</p>
              <p className="mt-2 font-semibold text-ink">{app.applicant_name || "—"}</p>
              <p className="font-mono text-xs text-muted">{app.reference}</p>
              <div className="mt-3 space-y-1 text-sm">
                <Row k="Loan" v={inr(form.loan_amount)} />
                <Row k="Income" v={inr(form.declared_income)} />
                <Row k="Documents" v={String(files.length)} />
              </div>
            </div>
          )}

        </aside>
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-muted">{k}</span>
      <span className="font-medium text-ink">{v}</span>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="label mb-1.5 block">{label}</label>
      {children}
    </div>
  );
}

function SectionTitle({ title, sub }: { title: string; sub: string }) {
  return (
    <div>
      <h2 className="font-semibold text-ink">{title}</h2>
      <p className="text-sm text-muted">{sub}</p>
    </div>
  );
}

function Steps({ steps, step }: { steps: string[]; step: number }) {
  return (
    <div className="flex items-center">
      {steps.map((l, i) => (
        <div key={l} className="flex flex-1 items-center">
          <div className="flex items-center gap-2.5">
            <div
              className={`grid h-8 w-8 place-items-center rounded-full text-xs font-bold transition ${
                step > i + 1
                  ? "bg-risk-low text-white"
                  : step === i + 1
                  ? "bg-navy-900 text-white"
                  : "border border-line bg-surface text-faint"
              }`}
            >
              {step > i + 1 ? "✓" : i + 1}
            </div>
            <span className={`text-sm font-semibold ${step >= i + 1 ? "text-ink" : "text-faint"}`}>{l}</span>
          </div>
          {i < steps.length - 1 && <div className={`mx-3 h-px flex-1 ${step > i + 1 ? "bg-risk-low/40" : "bg-line"}`} />}
        </div>
      ))}
    </div>
  );
}

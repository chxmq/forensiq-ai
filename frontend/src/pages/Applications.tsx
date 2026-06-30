import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Plus, Gauge, AlertTriangle, CheckCircle2, PlayCircle } from "lucide-react";
import { listApplications, batchAnalyze, type ApplicationSummary } from "../lib/api";
import { inr, titleCase, riskColor } from "../lib/format";
import { palette, riskColor as riskPalette } from "../lib/theme";
import { RiskBar, StatusPill, Avatar, Spinner, EmptyState } from "../components/common";

export default function Applications() {
  const [searchParams] = useSearchParams();
  const [apps, setApps] = useState<ApplicationSummary[] | null>(null);
  const [q, setQ] = useState(() => searchParams.get("q") || "");
  const [status, setStatus] = useState("all");
  const [risk, setRisk] = useState("all");
  const [batchBusy, setBatchBusy] = useState(false);

  const reload = () => listApplications().then(setApps).catch(() => setApps([]));

  useEffect(() => {
    setQ(searchParams.get("q") || "");
  }, [searchParams]);

  useEffect(() => {
    reload();
    const t = setInterval(reload, 8000);
    return () => clearInterval(t);
  }, []);

  const pending = apps?.filter((a) => !a.risk_band && a.status !== "analyzing") ?? [];

  const runBatch = async () => {
    setBatchBusy(true);
    try {
      await batchAnalyze();
      reload();
    } finally {
      setBatchBusy(false);
    }
  };

  const stats = useMemo(() => {
    if (!apps || apps.length === 0) return { clearRate: 0, highShare: 0, avg: 0 };
    const analyzed = apps.filter((a) => a.risk_band);
    const cleared = apps.filter((a) => a.status === "auto_cleared" || a.status === "approved").length;
    const high = analyzed.filter((a) => a.risk_band === "high" || a.risk_band === "critical").length;
    const avg = analyzed.reduce((s, a) => s + a.risk_score, 0) / Math.max(1, analyzed.length);
    return {
      clearRate: Math.round((cleared / apps.length) * 100),
      highShare: analyzed.length ? Math.round((high / analyzed.length) * 100) : 0,
      avg: Math.round(avg),
    };
  }, [apps]);

  if (!apps)
    return (
      <div className="grid h-[60vh] place-items-center">
        <Spinner label="Loading applications…" />
      </div>
    );

  const filtered = apps.filter((a) => {
    const mq =
      !q ||
      a.applicant_name.toLowerCase().includes(q.toLowerCase()) ||
      a.reference.toLowerCase().includes(q.toLowerCase());
    const ms = status === "all" || a.status === status;
    const mr = risk === "all" || a.risk_band === risk;
    return mq && ms && mr;
  });

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-ink">Applications Pipeline</h1>
          <p className="mt-1 text-sm text-muted">Manage and audit incoming risk assessments.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {pending.length > 0 && (
            <button className="btn-secondary" onClick={runBatch} disabled={batchBusy}>
              <PlayCircle className="h-4 w-4" />
              {batchBusy ? "Queuing…" : `Analyze ${pending.length} pending`}
            </button>
          )}
          <Link to="/new" className="btn-primary">
            <Plus className="h-4 w-4" /> New Application
          </Link>
        </div>
      </header>

      {pending.length > 0 && (
        <div className="card flex flex-wrap items-center justify-between gap-3 px-5 py-3">
          <p className="text-sm text-muted">
            <span className="font-semibold text-ink">{pending.length}</span> application(s) uploaded but not yet analyzed.
          </p>
          <button className="btn-primary" onClick={runBatch} disabled={batchBusy}>
            <PlayCircle className="h-4 w-4" /> Run batch analysis
          </button>
        </div>
      )}

      {/* Filters */}
      <div className="card grid gap-4 p-4 sm:grid-cols-3">
        <Field label="Search">
          <input className="input" placeholder="Applicant or reference…" value={q} onChange={(e) => setQ(e.target.value)} />
        </Field>
        <Field label="Status">
          <select className="input" value={status} onChange={(e) => setStatus(e.target.value)}>
            {["all", "auto_cleared", "manual_review", "escalated", "approved", "declined", "draft"].map((s) => (
              <option key={s} value={s}>{s === "all" ? "All Statuses" : titleCase(s)}</option>
            ))}
          </select>
        </Field>
        <Field label="Risk Level">
          <select className="input" value={risk} onChange={(e) => setRisk(e.target.value)}>
            {["all", "low", "medium", "high", "critical"].map((s) => (
              <option key={s} value={s}>{s === "all" ? "All Levels" : titleCase(s)}</option>
            ))}
          </select>
        </Field>
      </div>

      {/* Table */}
      {filtered.length === 0 ? (
        <EmptyState title="No applications match your filters" />
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left">
                <th className="th">Applicant</th>
                <th className="th">Reference</th>
                <th className="th">Loan Amount</th>
                <th className="th">Status</th>
                <th className="th">Risk Score</th>
                <th className="th text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((a) => (
                <tr key={a.id} className="group relative border-b border-line-soft last:border-0 hover:bg-canvas">
                  <td className="py-3 pl-5 pr-4">
                    <span
                      className="absolute left-0 top-2 h-[calc(100%-16px)] w-1 rounded-r"
                      style={{ background: a.risk_band ? riskColor[a.risk_band] : palette.faint }}
                    />
                    <Link to={`/applications/${a.id}`} className="flex items-center gap-3">
                      <Avatar name={a.applicant_name} />
                      <div>
                        <p className="font-semibold text-ink group-hover:text-brand-500">{a.applicant_name}</p>
                        <p className="text-xs text-faint">{titleCase(a.loan_type)}</p>
                      </div>
                    </Link>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-muted">{a.reference}</td>
                  <td className="px-4 py-3 font-medium text-ink">{inr(a.loan_amount)}</td>
                  <td className="px-4 py-3"><StatusPill status={a.status} /></td>
                  <td className="px-4 py-3">
                    {a.risk_band ? <RiskBar score={a.risk_score} band={a.risk_band} /> : <span className="text-xs text-faint">Pending</span>}
                  </td>
                  <td className="px-5 py-3 text-right">
                    <Link to={`/applications/${a.id}`} className="text-sm font-semibold text-brand-500 hover:underline">
                      View Report
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Metric cards */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Metric icon={<CheckCircle2 className="h-4 w-4" />} label="Auto-Clear Rate" value={`${stats.clearRate}%`} sub="Applications fast-tracked without manual review" color={riskPalette.low} />
        <Metric icon={<AlertTriangle className="h-4 w-4" />} label="High-Risk Share" value={`${stats.highShare}%`} sub="Analyzed applications at high/critical risk" color={riskPalette.critical} />
        <Metric icon={<Gauge className="h-4 w-4" />} label="Average Risk" value={`${stats.avg}`} sub="Mean integrity risk across analyzed apps" color={palette.brand[500]} />
      </div>
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

function Metric({ icon, label, value, sub, color }: { icon: React.ReactNode; label: string; value: string; sub: string; color: string }) {
  return (
    <div className="card card-pad">
      <p className="flex items-center gap-1.5 text-label-caps uppercase" style={{ color }}>
        {icon}
        {label}
      </p>
      <p className="mt-2 text-2xl font-extrabold text-ink">{value}</p>
      <p className="mt-1 text-xs text-muted">{sub}</p>
    </div>
  );
}

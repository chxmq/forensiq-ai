import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Cell,
  Tooltip,
} from "recharts";
import {
  CalendarClock,
  CheckCircle2,
  AlertTriangle,
  FileText,
  ArrowRight,
  Sparkles,
  ShieldAlert,
  TrendingUp,
} from "lucide-react";
import { getDashboard, type DashboardStats } from "../lib/api";
import { inr, riskColor, titleCase } from "../lib/format";
import { chart, palette, riskColor as riskPalette } from "../lib/theme";
import { StatCard, StatusPill, Avatar, RiskBar, ScoreRing, Spinner } from "../components/common";

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);

  useEffect(() => {
    const load = () => getDashboard().then(setStats).catch(() => {});
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, []);

  if (!stats)
    return (
      <div className="grid h-[60vh] place-items-center">
        <Spinner label="Loading control center…" />
      </div>
    );

  const dist = (["low", "medium", "high", "critical"] as const).map((k) => ({
    name: titleCase(k),
    key: k,
    value: stats.risk_distribution[k] || 0,
  }));
  const today = new Date().toLocaleDateString("en-IN", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  const topRisk = stats.recent.find((a) => a.risk_band === "critical" || a.risk_band === "high");

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-ink">Underwriting Control Center</h1>
          <p className="mt-1 text-sm text-muted">{today}</p>
        </div>
        <Link to="/new" className="btn-primary">
          <Sparkles className="h-4 w-4" /> Run New Analysis
        </Link>
      </header>

      <section className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <StatCard
          label="Total Applications"
          value={stats.total_applications}
          sub={`${stats.analyzing} analyzing · ${stats.pending_analysis} pending`}
          icon={<FileText className="h-[18px] w-[18px]" />}
        />
        <StatCard
          label="Findings Detected"
          value={stats.total_findings}
          sub={`${stats.high_severity_findings} high/critical`}
          icon={<ShieldAlert className="h-[18px] w-[18px]" />}
        />
        <StatCard
          label="Cleared"
          value={stats.auto_cleared}
          sub="Fast-tracked, low risk"
          icon={<CheckCircle2 className="h-[18px] w-[18px]" />}
        />
        <StatCard
          label="Escalated"
          value={stats.escalated}
          sub={`${stats.open_cases} open investigations`}
          icon={<AlertTriangle className="h-[18px] w-[18px]" />}
          tone="danger"
        />
        <StatCard
          tone="dark"
          label="Portfolio Avg Risk"
          icon={<CalendarClock className="h-[18px] w-[18px]" />}
          value={
            <div className="flex items-center gap-3">
              <ScoreRing score={stats.avg_risk_score} size={64} dark />
              <div>
                <p className="text-2xl font-extrabold text-white">{inr(stats.fraud_prevented_value)}</p>
                <p className="text-xs text-white/60">value at risk intercepted</p>
              </div>
            </div>
          }
        />
      </section>

      <section className="grid gap-6 lg:grid-cols-3">
        <div className="card card-pad lg:col-span-2">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-semibold text-ink">Applications by Risk Level</h2>
            <div className="flex gap-3 text-xs text-muted">
              {dist.map((d) => (
                <span key={d.key} className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full" style={{ background: riskColor[d.key] }} />
                  {d.name}
                </span>
              ))}
            </div>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={dist} margin={{ top: 8, right: 8, left: -20, bottom: 0 }} barCategoryGap="35%">
                <XAxis dataKey="name" tick={{ fill: chart.tick, fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis allowDecimals={false} tick={{ fill: chart.tickLight, fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip cursor={{ fill: chart.cursor }} contentStyle={{ borderRadius: 10, border: `1px solid ${chart.tooltipBorder}`, fontSize: 12, background: chart.tooltipBg }} />
                <Bar dataKey="value" radius={[6, 6, 0, 0]} maxBarSize={64}>
                  {dist.map((d) => (
                    <Cell key={d.key} fill={riskColor[d.key]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card card-pad">
          <h2 className="mb-3 font-semibold text-ink">Portfolio Alerts</h2>
          <div className="space-y-3">
            {topRisk && (
              <Insight
                accent={riskPalette.critical}
                tag="Anomaly Detected"
                body={`${topRisk.applicant_name} (${topRisk.reference}) flagged ${topRisk.risk_band?.toUpperCase()} at ${topRisk.risk_score.toFixed(0)}/100.`}
                action={<Link to={`/applications/${topRisk.id}`} className="font-semibold text-brand-500 hover:underline">Investigate →</Link>}
              />
            )}
            <Insight
              icon={<ShieldAlert className="h-4 w-4" />}
              tag="Active Investigations"
              body={`${stats.open_cases} case(s) open. ${inr(stats.fraud_prevented_value)} of exposure under review.`}
              action={<Link to="/cases" className="font-semibold text-brand-500 hover:underline">Open queue →</Link>}
            />
            <Insight
              icon={<TrendingUp className="h-4 w-4" />}
              tag="Detection Summary"
              body={`${stats.total_findings} integrity finding(s) across ${stats.total_applications} applications — ${stats.high_severity_findings} require immediate attention.`}
            />
          </div>
        </div>
      </section>

      <section className="card">
        <div className="flex items-center justify-between px-5 py-4">
          <h2 className="font-semibold text-ink">Recent Applications</h2>
          <Link to="/applications" className="text-sm font-semibold text-brand-500 hover:underline">
            View all <ArrowRight className="inline h-3.5 w-3.5" />
          </Link>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-y border-line text-left">
              <th className="th">Applicant</th>
              <th className="th">Reference</th>
              <th className="th">Loan Amount</th>
              <th className="th">Status</th>
              <th className="th">Risk Score</th>
              <th className="th"></th>
            </tr>
          </thead>
          <tbody>
            {stats.recent.map((a) => (
              <tr key={a.id} className="group border-b border-line-soft last:border-0 hover:bg-canvas">
                <td className="px-4 py-3">
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
                  {a.risk_band ? <RiskBar score={a.risk_score} band={a.risk_band} /> : <span className="text-xs text-faint">—</span>}
                </td>
                <td className="px-4 py-3 text-right">
                  <Link to={`/applications/${a.id}`} className="text-sm font-semibold text-brand-500 hover:underline">
                    View
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

function Insight({
  tag,
  body,
  action,
  accent,
  icon,
}: {
  tag: string;
  body: string;
  action?: React.ReactNode;
  accent?: string;
  icon?: React.ReactNode;
}) {
  return (
    <div
      className="rounded-lg border border-line bg-canvas p-3"
      style={accent ? { borderLeft: `3px solid ${accent}` } : undefined}
    >
      <p className="flex items-center gap-1.5 text-label-caps uppercase" style={{ color: accent || palette.muted }}>
        {icon}
        {tag}
      </p>
      <p className="mt-1 text-sm text-ink">{body}</p>
      {action && <div className="mt-1.5 text-xs">{action}</div>}
    </div>
  );
}

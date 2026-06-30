import { initials } from "../lib/format";
import { palette, riskColor, riskTint, statusColor, chart } from "../lib/theme";
import type { Severity } from "../lib/api";

export function RiskBadge({ band, score }: { band?: Severity | string | null; score?: number }) {
  const b = (band || "low") as string;
  const color = riskColor[b] || palette.muted;
  const tint = riskTint[b] || palette.lineSoft;
  return (
    <span className="chip" style={{ color, backgroundColor: tint }}>
      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: color }} />
      {b.toUpperCase()}
      {score != null && <span className="font-mono opacity-90">{score.toFixed(0)}</span>}
    </span>
  );
}

export function StatusPill({ status }: { status: string }) {
  const color = statusColor[status] || palette.muted;
  const label = status
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
  return (
    <span className="chip bg-canvas" style={{ color }}>
      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: color }} />
      {label}
    </span>
  );
}

export function SeverityDot({ severity }: { severity: Severity }) {
  return (
    <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: riskColor[severity] }} />
  );
}

export function Avatar({ name }: { name: string }) {
  return (
    <div className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-navy-900 font-mono text-[11px] font-bold text-white">
      {initials(name)}
    </div>
  );
}

/** Horizontal risk meter used in tables: a thin track + colored fill + number. */
export function RiskBar({ score, band }: { score: number; band?: string | null }) {
  const b = band || (score >= 75 ? "critical" : score >= 60 ? "high" : score >= 30 ? "medium" : "low");
  const color = riskColor[b];
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-28 overflow-hidden rounded-full bg-line-soft">
        <div className="h-full rounded-full" style={{ width: `${Math.max(4, score)}%`, background: color }} />
      </div>
      <span className="w-7 text-right font-mono text-sm font-bold" style={{ color }}>
        {score.toFixed(0)}
      </span>
    </div>
  );
}

export function ScoreRing({ score, size = 88, dark = false }: { score: number; size?: number; dark?: boolean }) {
  const band = score >= 75 ? "critical" : score >= 60 ? "high" : score >= 30 ? "medium" : "low";
  const color = riskColor[band];
  const stroke = 7;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const offset = c - (score / 100) * c;
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} stroke={dark ? "rgba(255,255,255,0.15)" : chart.track} strokeWidth={stroke} fill="none" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke={color}
          strokeWidth={stroke}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 1s ease" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-mono text-xl font-extrabold" style={{ color: dark ? "#fff" : color }}>
          {score.toFixed(0)}
        </span>
      </div>
    </div>
  );
}

export function StatCard({
  label,
  value,
  sub,
  icon,
  tone = "default",
}: {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  icon?: React.ReactNode;
  tone?: "default" | "danger" | "dark";
}) {
  if (tone === "dark") {
    return (
      <div className="rounded-xl bg-navy-900 p-5 text-white shadow-card">
        <div className="flex items-start justify-between">
          <p className="text-label-caps uppercase text-white/50">{label}</p>
          {icon && <span className="text-white/40">{icon}</span>}
        </div>
        <div className="mt-3">{value}</div>
        {sub && <p className="mt-1 text-xs text-white/60">{sub}</p>}
      </div>
    );
  }
  const danger = tone === "danger";
  return (
    <div
      className={`card card-pad ${danger ? "border-risk-critical/30" : ""}`}
      style={danger ? { background: riskTint.critical } : undefined}
    >
      <div className="flex items-start justify-between">
        <p className={`text-label-caps uppercase ${danger ? "text-risk-critical" : "text-faint"}`}>{label}</p>
        {icon && <span className={danger ? "text-risk-critical/70" : "text-faint"}>{icon}</span>}
      </div>
      <p className={`mt-3 text-3xl font-extrabold tracking-tight ${danger ? "text-risk-critical" : "text-ink"}`}>
        {value}
      </p>
      {sub && <p className="mt-1 text-xs text-muted">{sub}</p>}
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 text-muted">
      <div className="h-5 w-5 animate-spin rounded-full border-2 border-brand-500/30 border-t-brand-500" />
      {label && <span className="text-sm">{label}</span>}
    </div>
  );
}

export function EmptyState({ title, sub }: { title: string; sub?: string }) {
  return (
    <div className="grid place-items-center rounded-xl border border-dashed border-line py-16 text-center">
      <p className="font-medium text-ink">{title}</p>
      {sub && <p className="mt-1 text-sm text-muted">{sub}</p>}
    </div>
  );
}

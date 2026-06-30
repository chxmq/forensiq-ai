/** Single source of truth for Forensiq AI colors (matches tailwind.config.js). */

export const palette = {
  canvas: "#f4f3ee",
  surface: "#ffffff",
  line: "#e6e3da",
  lineSoft: "#efece4",
  ink: "#0f172a",
  muted: "#64748b",
  faint: "#94a3b8",
  navy: {
    900: "#0f172a",
    800: "#1e293b",
    700: "#334155",
  },
  brand: {
    50: "#eff6ff",
    500: "#2563eb",
    600: "#1d4ed8",
  },
} as const;

export const riskColor: Record<string, string> = {
  low: "#059669",
  medium: "#d97706",
  high: "#ea580c",
  critical: "#dc2626",
};

export const riskTint: Record<string, string> = {
  low: "#ecfdf5",
  medium: "#fffbeb",
  high: "#fff7ed",
  critical: "#fef2f2",
};

export const statusColor: Record<string, string> = {
  draft: palette.faint,
  analyzing: palette.brand[500],
  analyzed: palette.muted,
  auto_cleared: riskColor.low,
  manual_review: riskColor.medium,
  escalated: riskColor.critical,
  approved: riskColor.low,
  declined: riskColor.critical,
};

export const caseStatusColor: Record<string, string> = {
  open: riskColor.high,
  investigating: palette.brand[500],
  resolved_clear: riskColor.low,
  resolved_fraud: riskColor.critical,
};

export const graphNodeColor: Record<string, { fill: string; ring: string }> = {
  applicant: { fill: palette.brand[500], ring: palette.brand[500] },
  application: { fill: palette.navy[700], ring: palette.navy[800] },
  property: { fill: riskColor.medium, ring: riskColor.medium },
  registry: { fill: riskColor.low, ring: riskColor.low },
  default: { fill: palette.muted, ring: palette.navy[700] },
};

export const graphEdgeColor: Record<string, string> = {
  verified: riskColor.low,
  contradiction: riskColor.critical,
  warning: riskColor.medium,
  neutral: palette.faint,
};

/** Recharts / SVG chrome aligned to warm paper theme */
export const chart = {
  tick: palette.muted,
  tickLight: palette.faint,
  grid: palette.lineSoft,
  cursor: palette.lineSoft,
  tooltipBg: palette.surface,
  tooltipBorder: palette.line,
  label: palette.ink,
  track: palette.lineSoft,
  benfordObserved: riskColor.critical,
  benfordExpected: palette.brand[500],
} as const;

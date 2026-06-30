import { titleCase } from "../lib/format";
import { palette, riskColor, riskTint } from "../lib/theme";

/**
 * Offline satellite land-use visualization.
 *
 * Renders a procedural top-down "aerial" view of the parcel driven entirely by
 * the remote-sensing metrics (built-up ratio, NDVI, structures). This runs with
 * NO internet access (a hard requirement) and — unlike live tiles — can never
 * contradict the analysis, because it is a direct rendering of what the
 * classifier observed.
 */
interface GisMetrics {
  claimed_use?: string;
  observed_use?: string;
  built_up_ratio?: number;
  ndvi?: number;
  water_ratio?: number;
  structures_detected?: number;
  change_since_prior?: string;
  imagery_date?: string;
  map?: { lat: number; lng: number };
}

const PALETTE: Record<string, { bg: string; accent: string }> = {
  residential: { bg: "#3f3a33", accent: "#d6cdbf" },
  commercial: { bg: "#33363f", accent: "#c7ccd6" },
  agricultural: { bg: "#1f3a1c", accent: "#5aa54a" },
  forest: { bg: "#11280f", accent: "#2f8f33" },
  vacant: { bg: "#4a3f30", accent: "#8a7a5c" },
  water: { bg: "#0e2a3a", accent: "#2f7fa5" },
  default: { bg: "#2a2f3a", accent: "#7a8290" },
};

// Deterministic PRNG so the render is stable across reloads.
function rng(seed: number) {
  let s = seed % 2147483647;
  if (s <= 0) s += 2147483646;
  return () => (s = (s * 16807) % 2147483647) / 2147483647;
}

export default function PropertyMap({ metrics }: { metrics: GisMetrics }) {
  const claimed = metrics.claimed_use || "—";
  const observed = metrics.observed_use || "—";
  const mismatch = claimed !== observed && claimed !== "—" && observed !== "—";
  const pal = PALETTE[observed] || PALETTE.default;
  const built = metrics.built_up_ratio ?? 0;
  const ndvi = metrics.ndvi ?? 0;
  const lat = metrics.map?.lat;
  const lng = metrics.map?.lng;

  const W = 520;
  const H = 300;
  const rand = rng(Math.round((built * 1000 + ndvi * 777 + (lat || 1) * 13) | 0) || 7);

  const cells = [];
  const cols = 13;
  const rows = 7;
  const cw = W / cols;
  const ch = H / rows;
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const v = rand();
      cells.push({ x: c * cw, y: r * ch, v });
    }
  }

  return (
    <div className="space-y-3">
      <div className="relative overflow-hidden rounded-xl border border-line" style={{ background: pal.bg }}>
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ display: "block" }}>
          {/* land texture */}
          {cells.map((cell, i) => {
            // structures appear when built-up; vegetation when NDVI high
            const isStructure = cell.v < built;
            const isVeg = !isStructure && cell.v > 1 - ndvi;
            if (isStructure) {
              const pad = cw * 0.18;
              return (
                <rect
                  key={i}
                  x={cell.x + pad}
                  y={cell.y + pad}
                  width={cw - pad * 2}
                  height={ch - pad * 2}
                  rx={2}
                  fill={pal.accent}
                  opacity={0.85}
                />
              );
            }
            if (isVeg) {
              return (
                <circle key={i} cx={cell.x + cw / 2} cy={cell.y + ch / 2} r={Math.min(cw, ch) * 0.32} fill={pal.accent} opacity={0.55} />
              );
            }
            return (
              <rect key={i} x={cell.x} y={cell.y} width={cw} height={ch} fill={pal.accent} opacity={cell.v * 0.06} />
            );
          })}

          {/* water overlay */}
          {(metrics.water_ratio ?? 0) > 0.1 && (
            <rect x={0} y={H * 0.7} width={W} height={H * 0.3} fill="#2f7fa5" opacity={0.5} />
          )}

          {/* center marker */}
          <g transform={`translate(${W / 2}, ${H / 2})`}>
            <circle r={26} fill={mismatch ? riskColor.critical : riskColor.low} opacity={0.15} />
            <circle r={26} fill="none" stroke={mismatch ? riskColor.critical : riskColor.low} strokeWidth={2} />
            <circle r={5} fill={mismatch ? riskColor.critical : riskColor.low} />
          </g>

          {/* HUD */}
          <text x={12} y={22} fontSize={11} fill="#e2e8f0" fontFamily="monospace" opacity={0.9}>
            ◉ SAT-IMAGERY {metrics.imagery_date || ""}
          </text>
          {lat != null && (
            <text x={12} y={H - 12} fontSize={10} fill="#e2e8f0" fontFamily="monospace" opacity={0.8}>
              {lat.toFixed(4)}, {lng?.toFixed(4)} · built-up {(built * 100).toFixed(0)}% · NDVI {ndvi.toFixed(2)}
            </text>
          )}
        </svg>
        <div className="pointer-events-none absolute right-2 top-2 rounded-md bg-black/40 px-2 py-1 text-[10px] font-mono text-faint">
          OFFLINE LAND-USE RENDER
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-lg border border-line bg-canvas p-3">
          <p className="label">Claimed Land Use</p>
          <p className="text-sm font-bold text-ink">{titleCase(claimed)}</p>
        </div>
        <div
          className="rounded-lg border p-3"
          style={{
            borderColor: mismatch ? `${riskColor.critical}44` : palette.line,
            background: mismatch ? riskTint.critical : palette.canvas,
          }}
        >
          <p className="label">Satellite Observed</p>
          <p className="text-sm font-bold" style={{ color: mismatch ? riskColor.critical : palette.ink }}>
            {titleCase(observed)}
          </p>
        </div>
      </div>
      {mismatch && (
        <p className="rounded-lg bg-risk-critical/10 px-3 py-2 text-xs text-risk-critical">
          ⚠ Physical land use contradicts the claimed property type.
        </p>
      )}
    </div>
  );
}

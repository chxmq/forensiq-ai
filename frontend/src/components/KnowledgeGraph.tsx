import { graphEdgeColor, graphNodeColor, palette } from "../lib/theme";

interface GNode {
  id: string;
  label: string;
  type: string;
  source?: string;
}
interface GEdge {
  source: string;
  target: string;
  label: string;
  status: string;
}

export default function KnowledgeGraph({ graph }: { graph: { nodes: GNode[]; edges: GEdge[] } }) {
  const W = 720;
  const H = 380;
  const cx = W / 2;
  const cy = H / 2;
  const R = Math.min(W, H) / 2 - 80;

  const nodes = graph.nodes || [];
  const pos: Record<string, { x: number; y: number }> = {};
  nodes.forEach((n) => {
    if (n.id === "applicant") {
      pos[n.id] = { x: cx, y: cy };
    } else {
      const others = nodes.filter((m) => m.id !== "applicant");
      const idx = others.findIndex((m) => m.id === n.id);
      const angle = (idx / Math.max(1, others.length)) * Math.PI * 2 - Math.PI / 2;
      pos[n.id] = { x: cx + R * Math.cos(angle), y: cy + R * Math.sin(angle) };
    }
  });

  return (
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ minWidth: 560 }}>
        {(graph.edges || []).map((e, i) => {
          const a = pos[e.source];
          const b = pos[e.target];
          if (!a || !b) return null;
          const color = graphEdgeColor[e.status] || graphNodeColor.default.ring;
          const mx = (a.x + b.x) / 2;
          const my = (a.y + b.y) / 2;
          return (
            <g key={i}>
              <line
                x1={a.x}
                y1={a.y}
                x2={b.x}
                y2={b.y}
                stroke={color}
                strokeWidth={e.status === "contradiction" ? 2.5 : 1.5}
                strokeDasharray={e.status === "contradiction" ? "0" : "5 4"}
                opacity={0.8}
              />
              <rect x={mx - e.label.length * 3.2 - 6} y={my - 9} width={e.label.length * 6.4 + 12} height={18} rx={9} fill={palette.surface} stroke={color} strokeOpacity={0.6} />
              <text x={mx} y={my + 3.5} textAnchor="middle" fontSize={10} fill={color} fontWeight={600}>
                {e.label}
              </text>
            </g>
          );
        })}

        {nodes.map((n) => {
          const p = pos[n.id];
          const s = graphNodeColor[n.type] || graphNodeColor.default;
          return (
            <g key={n.id}>
              <circle cx={p.x} cy={p.y} r={28} fill={s.fill} fillOpacity={0.12} stroke={s.ring} strokeWidth={2} />
              <text x={p.x} y={p.y - 1} textAnchor="middle" fontSize={10.5} fontWeight={700} fill={palette.ink}>
                {n.label.length > 16 ? n.label.slice(0, 15) + "…" : n.label}
              </text>
              <text x={p.x} y={p.y + 12} textAnchor="middle" fontSize={8} fill={palette.muted}>
                {n.type}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

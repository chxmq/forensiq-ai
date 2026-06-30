import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { chart } from "../lib/theme";

export default function BenfordChart({
  observed,
  expected,
}: {
  observed: Record<string, number>;
  expected: Record<string, number>;
}) {
  const data = Array.from({ length: 9 }, (_, i) => {
    const d = String(i + 1);
    return {
      digit: d,
      Observed: +(observed[d] * 100).toFixed(1),
      "Benford Expected": +(expected[d] * 100).toFixed(1),
    };
  });
  return (
    <ResponsiveContainer width="100%" height={220}>
      <ComposedChart data={data} margin={{ top: 6, right: 8, left: -18, bottom: 0 }}>
        <XAxis dataKey="digit" tick={{ fill: chart.tick, fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fill: chart.tickLight, fontSize: 11 }} axisLine={false} tickLine={false} unit="%" />
        <Tooltip
          cursor={{ fill: chart.cursor }}
          contentStyle={{ background: chart.tooltipBg, border: `1px solid ${chart.tooltipBorder}`, borderRadius: 10, fontSize: 12 }}
          labelStyle={{ color: chart.label }}
        />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        <Bar dataKey="Observed" fill={chart.benfordObserved} radius={[4, 4, 0, 0]} maxBarSize={26} />
        <Line dataKey="Benford Expected" stroke={chart.benfordExpected} strokeWidth={2.5} dot={{ r: 3 }} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

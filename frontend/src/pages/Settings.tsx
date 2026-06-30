import { useEffect, useState } from "react";
import { Save, RotateCcw } from "lucide-react";
import { getPolicy, updatePolicy, type PolicyConfig } from "../lib/api";
import { Spinner } from "../components/common";

const DEFAULT: PolicyConfig = {
  weights: { document: 0.25, financial: 0.2, verification: 0.2, gis: 0.15, intake: 0.2 },
  thresholds: { approve: 30, review: 60, escalate: 75 },
};

export default function Settings() {
  const [policy, setPolicy] = useState<PolicyConfig | null>(null);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    getPolicy().then(setPolicy).catch(() => setPolicy(DEFAULT));
  }, []);

  if (!policy)
    return (
      <div className="grid h-[60vh] place-items-center">
        <Spinner label="Loading policy…" />
      </div>
    );

  const setWeight = (k: keyof PolicyConfig["weights"], v: number) =>
    setPolicy((p) => p && { ...p, weights: { ...p.weights, [k]: v } });

  const setThreshold = (k: keyof PolicyConfig["thresholds"], v: number) =>
    setPolicy((p) => p && { ...p, thresholds: { ...p.thresholds, [k]: v } });

  const save = async () => {
    setBusy(true);
    setSaved(false);
    try {
      const updated = await updatePolicy(policy);
      setPolicy(updated);
      setSaved(true);
    } finally {
      setBusy(false);
    }
  };

  const weightSum = Object.values(policy.weights).reduce((a, b) => a + b, 0);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header>
        <h1 className="text-3xl font-extrabold tracking-tight text-ink">Underwriting Policy</h1>
        <p className="mt-1 text-sm text-muted">
          Configure module weights and escalation thresholds. Changes apply to the next analysis run and persist locally.
        </p>
      </header>

      <section className="card card-pad space-y-5">
        <h2 className="font-semibold text-ink">Module Weights</h2>
        <p className="text-xs text-muted">Relative influence on the composite risk score (sum ≈ 1.0).</p>
        {(
          [
            ["document", "Document Forensics"],
            ["financial", "Financial Integrity"],
            ["verification", "Cross-Source Verification"],
            ["gis", "GIS / Satellite"],
            ["intake", "Document Pack Completeness"],
          ] as const
        ).map(([key, label]) => (
          <div key={key}>
            <div className="mb-1 flex justify-between text-sm">
              <span className="text-muted">{label}</span>
              <span className="font-mono font-semibold">{(policy.weights[key] * 100).toFixed(0)}%</span>
            </div>
            <input
              type="range"
              min={5}
              max={50}
              value={Math.round(policy.weights[key] * 100)}
              onChange={(e) => setWeight(key, Number(e.target.value) / 100)}
              className="w-full"
            />
          </div>
        ))}
        <p className={`text-xs ${Math.abs(weightSum - 1) > 0.05 ? "text-risk-critical" : "text-faint"}`}>
          Total weight: {weightSum.toFixed(2)}
        </p>
      </section>

      <section className="card card-pad space-y-5">
        <h2 className="font-semibold text-ink">Decision Thresholds</h2>
        <p className="text-xs text-muted">Risk score bands (0–100) for auto-clear, manual review, and escalation.</p>
        {(
          [
            ["approve", "Auto-clear below"],
            ["review", "Manual review from"],
            ["escalate", "Auto-escalate from"],
          ] as const
        ).map(([key, label]) => (
          <div key={key}>
            <label className="label mb-1.5 block">{label}</label>
            <input
              type="number"
              min={0}
              max={100}
              className="input max-w-xs"
              value={policy.thresholds[key]}
              onChange={(e) => setThreshold(key, Number(e.target.value))}
            />
          </div>
        ))}
      </section>

      <div className="flex flex-wrap gap-3">
        <button className="btn-primary" onClick={save} disabled={busy}>
          <Save className="h-4 w-4" /> {busy ? "Saving…" : "Save Policy"}
        </button>
        <button className="btn-secondary" onClick={() => setPolicy(DEFAULT)}>
          <RotateCcw className="h-4 w-4" /> Reset defaults
        </button>
        {saved && <span className="self-center text-sm text-risk-low">Saved — applies on next analysis.</span>}
      </div>
    </div>
  );
}

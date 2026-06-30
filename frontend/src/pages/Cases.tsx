import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ShieldAlert, CheckCircle2, XCircle, UserCog, Clock } from "lucide-react";
import { listCases, updateCase, type CaseOut } from "../lib/api";
import { fmtDate, riskColor, riskTint, titleCase } from "../lib/format";
import { caseStatusColor } from "../lib/theme";
import { Spinner, EmptyState } from "../components/common";

const STATUS_COLOR = caseStatusColor;

export default function Cases() {
  const [cases, setCases] = useState<CaseOut[] | null>(null);
  const [active, setActive] = useState<CaseOut | null>(null);
  const [note, setNote] = useState("");

  const load = () =>
    listCases().then((cs) => {
      setCases(cs);
      setActive((prev) => prev ?? cs[0] ?? null);
    }).catch(() => setCases([]));
  useEffect(() => {
    load();
  }, []);

  const act = async (c: CaseOut, status: string) => {
    const updated = await updateCase(c.id, { status, resolution_note: note, assignee: "underwriter" });
    setActive(updated);
    setNote("");
    load();
  };

  if (!cases)
    return (
      <div className="grid h-[60vh] place-items-center">
        <Spinner label="Loading investigations…" />
      </div>
    );

  const openCount = cases.filter((c) => c.status === "open" || c.status === "investigating").length;
  const closed = active && active.status !== "open" && active.status !== "investigating";

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-3xl font-extrabold tracking-tight text-ink">Investigations</h1>
        <p className="mt-1 text-sm text-muted">{openCount} open · {cases.length} total auto-escalated cases.</p>
      </header>

      {cases.length === 0 ? (
        <EmptyState title="No investigation cases" sub="High-risk applications are auto-escalated here." />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
          {/* Case list */}
          <div className="card overflow-hidden">
            <p className="border-b border-line px-4 py-3 text-label-caps uppercase text-faint">Open Cases</p>
            <div className="max-h-[70vh] divide-y divide-line-soft overflow-y-auto">
              {cases.map((c) => (
                <button
                  key={c.id}
                  onClick={() => setActive(c)}
                  className={`relative block w-full px-4 py-3.5 text-left transition hover:bg-canvas ${
                    active?.id === c.id ? "bg-canvas" : ""
                  }`}
                >
                  {active?.id === c.id && <span className="absolute left-0 top-0 h-full w-1" style={{ background: riskColor[c.priority] }} />}
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-bold text-faint">{c.case_number}</span>
                    <span className="chip" style={{ color: riskColor[c.priority], background: riskTint[c.priority] }}>
                      {c.priority.toUpperCase()}
                    </span>
                  </div>
                  {c.applicant_name && (
                    <p className="mt-1 text-sm font-semibold text-ink">
                      {c.applicant_name}
                      {c.application_reference && (
                        <span className="ml-2 font-mono text-xs font-normal text-faint">{c.application_reference}</span>
                      )}
                    </p>
                  )}
                  <p className="mt-1 line-clamp-2 text-sm text-muted">{c.summary}</p>
                  <div className="mt-2 flex items-center justify-between text-[11px]">
                    <span className="font-semibold" style={{ color: STATUS_COLOR[c.status] }}>{titleCase(c.status)}</span>
                    <span className="flex items-center gap-1 text-faint"><Clock className="h-3 w-3" /> {fmtDate(c.created_at)}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Detail */}
          <div>
            {active ? (
              <div className="card card-pad space-y-5">
                <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line pb-4">
                  <div className="flex items-center gap-3">
                    <div className="grid h-10 w-10 place-items-center rounded-lg" style={{ background: riskTint[active.priority] }}>
                      <ShieldAlert className="h-5 w-5" style={{ color: riskColor[active.priority] }} />
                    </div>
                    <div>
                      <h2 className="font-mono text-lg font-bold text-ink">{active.case_number}</h2>
                      <p className="text-xs text-faint">Opened {fmtDate(active.created_at)}</p>
                    </div>
                  </div>
                  <span className="chip" style={{ color: riskColor[active.priority], background: riskTint[active.priority] }}>
                    {active.priority.toUpperCase()} PRIORITY
                  </span>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <Block label="Status">
                    <span className="font-semibold" style={{ color: STATUS_COLOR[active.status] }}>{titleCase(active.status)}</span>
                  </Block>
                  <Block label="Assignee">
                    <span className="flex items-center gap-1.5 text-ink">
                      <UserCog className="h-4 w-4 text-faint" /> {active.assignee || "Unassigned"}
                    </span>
                  </Block>
                </div>

                <Block label="Risk Summary">
                  <p className="text-sm leading-relaxed text-muted">{active.summary}</p>
                  {active.application_id && (
                    <Link
                      to={`/applications/${active.application_id}`}
                      className="mt-3 inline-flex text-sm font-semibold text-brand-600 hover:underline"
                    >
                      Open application →
                    </Link>
                  )}
                </Block>

                {active.resolution_note && (
                  <div className="rounded-lg border border-line bg-canvas p-3">
                    <p className="label mb-1">Resolution Note</p>
                    <p className="text-sm text-muted">{active.resolution_note}</p>
                  </div>
                )}

                {closed ? (
                  <div className="rounded-lg border border-line bg-canvas p-3 text-center text-sm text-muted">
                    Case closed · {titleCase(active.status)}
                  </div>
                ) : (
                  <div className="space-y-3 border-t border-line pt-4">
                    <textarea
                      className="input min-h-[88px]"
                      placeholder="Investigation note / resolution rationale…"
                      value={note}
                      onChange={(e) => setNote(e.target.value)}
                    />
                    <div className="flex flex-wrap gap-2">
                      {active.status === "open" && (
                        <button className="btn-secondary" onClick={() => act(active, "investigating")}>
                          Start Investigation
                        </button>
                      )}
                      <button className="btn-success" onClick={() => act(active, "resolved_clear")}>
                        <CheckCircle2 className="h-4 w-4" /> Resolve — Clear
                      </button>
                      <button className="btn-danger" onClick={() => act(active, "resolved_fraud")}>
                        <XCircle className="h-4 w-4" /> Confirm Fraud
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <EmptyState title="Select a case" sub="Choose an investigation to view details and take action." />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function Block({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="label mb-1">{label}</p>
      {children}
    </div>
  );
}

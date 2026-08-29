import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { approveRule, ApiError, getRuleComparison, rejectRule, RuleComparison as Comparison } from "../api";

// admin-dashboard change, task 4.7 — side-by-side comparison, material
// changes visually distinguished from cosmetic ones, approve/reject
// with a reason field on reject.
export function RuleComparison() {
  const { id } = useParams<{ id: string }>();
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [reason, setReason] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  function load() {
    if (!id) return;
    setLoading(true);
    getRuleComparison(id)
      .then(setComparison)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load comparison."))
      .finally(() => setLoading(false));
  }

  useEffect(load, [id]);

  async function handleApprove() {
    if (!id) return;
    setActionError(null);
    setSubmitting(true);
    try {
      await approveRule(id);
      load();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Approve failed.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleReject() {
    if (!id) return;
    if (!reason.trim()) {
      setActionError("A rejection requires a reason.");
      return;
    }
    setActionError(null);
    setSubmitting(true);
    try {
      await rejectRule(id, reason);
      setReason("");
      load();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Reject failed.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <p>Loading…</p>;
  if (error) return <p className="error">{error}</p>;
  if (!comparison) return null;

  const materialDiffs = comparison.diffs.filter((d) => d.materiality === "material");
  const cosmeticDiffs = comparison.diffs.filter((d) => d.materiality === "cosmetic");

  return (
    <div>
      <button className="secondary" onClick={() => navigate("/rules")}>
        ← Back to pending queue
      </button>
      <h2>
        {comparison.pending.service_name} — <span className={`pill ${comparison.pending.status}`}>{comparison.pending.status}</span>
      </h2>

      <div className="card">
        <h3>Differences</h3>
        {comparison.diffs.length === 0 ? (
          <p className="note">No differences detected.</p>
        ) : (
          <>
            {materialDiffs.map((d, i) => (
              <div key={`m-${i}`} className="diff-row material" style={{ padding: "0.4rem 0.6rem", marginBottom: "0.35rem", borderRadius: 4 }}>
                <strong>Material —</strong> {d.field}: <code>{JSON.stringify(d.approved_value)}</code> →{" "}
                <code>{JSON.stringify(d.draft_value)}</code>
              </div>
            ))}
            {cosmeticDiffs.map((d, i) => (
              <div key={`c-${i}`} className="diff-row cosmetic" style={{ padding: "0.3rem 0.6rem", marginBottom: "0.25rem", borderRadius: 4, fontSize: "0.85rem" }}>
                Cosmetic — {d.field}: {JSON.stringify(d.approved_value)} → {JSON.stringify(d.draft_value)}
              </div>
            ))}
          </>
        )}
      </div>

      <div className="grid-2">
        <PayloadColumn title="Approved (live)" payload={comparison.approved} />
        <PayloadColumn title="Draft (proposed)" payload={comparison.draft} />
      </div>

      <div className="card">
        <h3>Decision</h3>
        {actionError && <p className="error">{actionError}</p>}
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "flex-start" }}>
          <button onClick={handleApprove} disabled={submitting}>
            Approve
          </button>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem" }}>
            <textarea
              placeholder="Reason for rejection"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={2}
              style={{ width: 260 }}
            />
            <button className="danger" onClick={handleReject} disabled={submitting}>
              Reject
            </button>
          </div>
        </div>
        {comparison.pending.reason && (
          <p className="note">Recorded reason: {comparison.pending.reason}</p>
        )}
        <p className="note">
          Approving/rejecting here records an action in the dashboard only — it never changes the
          live rule version's status.
        </p>
      </div>
    </div>
  );
}

function PayloadColumn({ title, payload }: { title: string; payload: Comparison["approved"] }) {
  return (
    <div className="card">
      <h3>{title}</h3>
      {payload.note && <p className="note">{payload.note}</p>}
      {payload.fee && (
        <p>
          Fee ({String(payload.fee.basis)}): {String(payload.fee.currency)}{" "}
          {Number(payload.fee.base_amount).toLocaleString()}
          {payload.fee.penalty_amount ? ` + ${Number(payload.fee.penalty_amount).toLocaleString()} penalty` : ""}
        </p>
      )}
      <ul>
        {payload.requirements.map((r, i) => {
          const citation = r.citation as { source_url?: string; verified_at?: string | null } | undefined;
          return (
            <li key={i}>
              {String(r.label)} <span className="note">({String(r.kind)})</span>
              {citation?.source_url && (
                <div className="citation">
                  <a href={citation.source_url} target="_blank" rel="noreferrer">
                    source
                  </a>
                  {citation.verified_at && ` — verified ${new Date(citation.verified_at).toLocaleDateString()}`}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

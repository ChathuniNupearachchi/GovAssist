import { useEffect, useState } from "react";
import { ApiError, getPlanAudit, PlanAudit as PlanAuditRow } from "../api";

// admin-dashboard change, task 8.2 — flags outdated plans distinctly
// from current ones.
export function PlanAudit() {
  const [rows, setRows] = useState<PlanAuditRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getPlanAudit()
      .then(setRows)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load plan audit."))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p>Loading…</p>;
  if (error) return <p className="error">{error}</p>;
  if (rows.length === 0) return <p className="note">No resolved cases to audit yet.</p>;

  return (
    <div>
      <h2>Saved plans vs. rule versions</h2>
      <table>
        <thead>
          <tr>
            <th>Case</th>
            <th>Service</th>
            <th>Resolved</th>
            <th>Resolved against</th>
            <th>Current approved</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.case_id}>
              <td>{r.case_id.slice(0, 8)}</td>
              <td>{r.service_name}</td>
              <td>{new Date(r.resolved_at).toLocaleDateString()}</td>
              <td>
                v{r.resolved_rule_version_number} ({r.resolved_rule_version_status})
              </td>
              <td>{r.current_approved_rule_version_number ? `v${r.current_approved_rule_version_number}` : "—"}</td>
              <td>
                {r.outdated ? (
                  <span className="pill outdated">outdated</span>
                ) : (
                  <span className="pill approved">current</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

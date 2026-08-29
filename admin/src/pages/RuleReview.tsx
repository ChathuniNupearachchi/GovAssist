import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listPendingRules, PendingRule, ApiError } from "../api";

// admin-dashboard change, task 4.6 — the pending queue.
export function RuleReview() {
  const [pending, setPending] = useState<PendingRule[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    listPendingRules()
      .then(setPending)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load pending rules."))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p>Loading…</p>;
  if (error) return <p className="error">{error}</p>;

  return (
    <div>
      <h2>Rule review</h2>
      {pending.length === 0 ? (
        <p className="note">Nothing pending review.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Service</th>
              <th>Source</th>
              <th>Status</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {pending.map((p) => (
              <tr key={p.id} className="clickable" onClick={() => navigate(`/rules/${p.id}`)}>
                <td>{p.service_name}</td>
                <td>{p.source === "admin_draft" ? "Draft (seeded)" : "Live draft rule version"}</td>
                <td>
                  <span className={`pill ${p.status}`}>{p.status}</span>
                </td>
                <td>{p.created_at ? new Date(p.created_at).toLocaleString() : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

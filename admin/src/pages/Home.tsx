import { useEffect, useState } from "react";
import { DashboardSummary, getDashboardSummary, ApiError } from "../api";

// admin-dashboard change, tasks 5.2-5.3 — operational status only. No
// RAGAS or Langfuse panel anywhere on this page: both are developer
// tooling with their own dedicated interfaces, and neither answers a
// reviewer's actual question of whether a specific fee, document, or
// office is correct (design.md).
export function Home() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getDashboardSummary()
      .then(setSummary)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load dashboard."))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p>Loading…</p>;
  if (error) return <p className="error">{error}</p>;
  if (!summary) return <p>No data.</p>;

  return (
    <div>
      <h2>Dashboard</h2>
      <div className="grid-2">
        <div className="card">
          <h3>Drafts pending review</h3>
          <p style={{ fontSize: "2rem", margin: 0 }}>{summary.drafts_pending}</p>
        </div>
        <div className="card">
          <h3>Sources not yet approved</h3>
          <p style={{ fontSize: "2rem", margin: 0 }}>{summary.sources_pending}</p>
        </div>
        <div className="card">
          <h3>Services with no approved rule version</h3>
          <p style={{ fontSize: "2rem", margin: 0 }}>{summary.services_without_approved_rule}</p>
        </div>
      </div>

      <div className="card">
        <h3>Recently approved</h3>
        {summary.recently_approved.length === 0 ? (
          <p className="note">Nothing approved yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Target</th>
                <th>Action</th>
                <th>By</th>
                <th>When</th>
              </tr>
            </thead>
            <tbody>
              {summary.recently_approved.map((a) => (
                <tr key={a.id}>
                  <td>
                    {a.target_type} / {a.target_id.slice(0, 8)}
                  </td>
                  <td>{a.action}</td>
                  <td>{a.admin_email}</td>
                  <td>{new Date(a.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

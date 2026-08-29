import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, listServices, ServiceSummary } from "../api";

// admin-dashboard change, task 6.5 — service list. Per
// admin-service-catalog spec's "Hand-verified rules display as
// approved": a service's current rule version status is shown exactly
// as `/admin/services` returns it — never overridden to "pending".
export function Services() {
  const [services, setServices] = useState<ServiceSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    listServices()
      .then(setServices)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load services."))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p>Loading…</p>;
  if (error) return <p className="error">{error}</p>;
  if (services.length === 0) return <p className="note">No services found.</p>;

  return (
    <div>
      <h2>Services</h2>
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Code</th>
            <th>Category</th>
            <th>Requirements</th>
            <th>Conditions</th>
            <th>Questions</th>
            <th>Rule version</th>
            <th>Verified</th>
          </tr>
        </thead>
        <tbody>
          {services.map((s) => (
            <tr key={s.id} className="clickable" onClick={() => navigate(`/services/${s.id}`)}>
              <td>{s.name}</td>
              <td>{s.code}</td>
              <td>{s.category}</td>
              <td>{s.requirement_count}</td>
              <td>{s.condition_count}</td>
              <td>{s.question_count}</td>
              <td>
                v{s.current_rule_version_number ?? "—"}{" "}
                {s.current_rule_version_status && (
                  <span className={`pill ${s.current_rule_version_status}`}>{s.current_rule_version_status}</span>
                )}
              </td>
              <td>{s.last_verified_at ? new Date(s.last_verified_at).toLocaleDateString() : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

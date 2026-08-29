import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ApiError, getService, ServiceDetail as Detail, writeServiceOverlay } from "../api";

// admin-dashboard change, tasks 6.5 — drill-down with citations, plus
// an overlay-edit form. Per admin-service-catalog spec's "Catalog
// edits are overlay-only": submitting this form writes only an
// ADMIN_OVERLAY row (shown below in "Dashboard-only edits"); the live
// SERVICE/RULE_VERSION/REQUIREMENT rows above it never change.
export function ServiceDetail() {
  const { id } = useParams<{ id: string }>();
  const [service, setService] = useState<Detail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [overlayName, setOverlayName] = useState("");
  const [overlayError, setOverlayError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  function load() {
    if (!id) return;
    setLoading(true);
    getService(id)
      .then((s) => {
        setService(s);
        setOverlayName(s.name);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load service."))
      .finally(() => setLoading(false));
  }

  useEffect(load, [id]);

  async function handleOverlaySubmit() {
    if (!id) return;
    setOverlayError(null);
    setSubmitting(true);
    try {
      await writeServiceOverlay(id, "update", { name: overlayName });
      load();
    } catch (err) {
      setOverlayError(err instanceof ApiError ? err.message : "Overlay edit failed.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <p>Loading…</p>;
  if (error) return <p className="error">{error}</p>;
  if (!service) return null;

  return (
    <div>
      <button className="secondary" onClick={() => navigate("/services")}>
        ← Back to services
      </button>
      <h2>
        {service.name}{" "}
        {service.current_rule_version_status && (
          <span className={`pill ${service.current_rule_version_status}`}>{service.current_rule_version_status}</span>
        )}
      </h2>
      <p className="note">
        {service.code} · v{service.current_rule_version_number ?? "—"} · last verified{" "}
        {service.last_verified_at ? new Date(service.last_verified_at).toLocaleDateString() : "—"}
      </p>

      <div className="card">
        <h3>Requirements</h3>
        <table>
          <thead>
            <tr>
              <th>Label</th>
              <th>Kind</th>
              <th>Seq</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            {service.requirements.map((r) => (
              <tr key={r.id}>
                <td>{r.label}</td>
                <td>{r.kind}</td>
                <td>{r.sequence}</td>
                <td className="citation">
                  <a href={r.citation.source_url} target="_blank" rel="noreferrer">
                    source
                  </a>
                  {r.citation.verified_at && ` — ${new Date(r.citation.verified_at).toLocaleDateString()}`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3>Fee rules</h3>
        <table>
          <thead>
            <tr>
              <th>Basis</th>
              <th>Amount</th>
              <th>Penalty</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            {service.fee_rules.map((f) => (
              <tr key={f.id}>
                <td>{f.basis}</td>
                <td>
                  {f.currency} {f.base_amount.toLocaleString()}
                </td>
                <td>{f.penalty_amount ? f.penalty_amount.toLocaleString() : "—"}</td>
                <td className="citation">
                  <a href={f.citation.source_url} target="_blank" rel="noreferrer">
                    source
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3>Questions &amp; conditions</h3>
        <table>
          <thead>
            <tr>
              <th>Prompt</th>
              <th>Type</th>
            </tr>
          </thead>
          <tbody>
            {service.questions.map((q) => (
              <tr key={q.id}>
                <td>{q.prompt}</td>
                <td>{q.answer_type}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="note">{service.conditions.length} condition(s) across these questions.</p>
      </div>

      <div className="card">
        <h3>Edit (dashboard-only)</h3>
        {overlayError && <p className="error">{overlayError}</p>}
        <div className="form-row">
          <label htmlFor="overlay-name">Proposed name</label>
          <input id="overlay-name" value={overlayName} onChange={(e) => setOverlayName(e.target.value)} />
        </div>
        <button onClick={handleOverlaySubmit} disabled={submitting}>
          Save as dashboard overlay
        </button>
        <p className="note">
          This never changes the live service — it's recorded as an overlay and shown below only in
          this dashboard's own view.
        </p>
        {service.overlays.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>Operation</th>
                <th>Payload</th>
                <th>When</th>
              </tr>
            </thead>
            <tbody>
              {service.overlays.map((o) => (
                <tr key={o.id}>
                  <td>{o.operation}</td>
                  <td>{JSON.stringify(o.payload)}</td>
                  <td>{new Date(o.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

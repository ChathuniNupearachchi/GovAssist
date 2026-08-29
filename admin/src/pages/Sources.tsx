import { FormEvent, useEffect, useState } from "react";
import { addSourceOverlay, ApiError, listSources, SourceDoc } from "../api";

// admin-dashboard change, task 7.4 — source list with extraction
// method shown per row, and an add-source form with a visible "not yet
// ingested" note (per admin-source-catalog spec's "Adding a source
// records intent without live ingestion").
export function Sources() {
  const [sources, setSources] = useState<SourceDoc[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [url, setUrl] = useState("");
  const [docType, setDocType] = useState<"html" | "pdf">("html");
  const [addedNote, setAddedNote] = useState<string | null>(null);
  const [addError, setAddError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function load() {
    setLoading(true);
    listSources()
      .then(setSources)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load sources."))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  async function handleAdd(e: FormEvent) {
    e.preventDefault();
    setAddError(null);
    setAddedNote(null);
    setSubmitting(true);
    try {
      await addSourceOverlay(url, docType);
      setAddedNote(
        `Recorded as a pending overlay. Live ingestion was NOT triggered — this source will not appear ` +
          `in the list above until a real scrape/upload is run separately.`,
      );
      setUrl("");
    } catch (err) {
      setAddError(err instanceof ApiError ? err.message : "Failed to add source.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <h2>Sources</h2>

      {loading && <p>Loading…</p>}
      {error && <p className="error">{error}</p>}
      {!loading && !error && (
        <table>
          <thead>
            <tr>
              <th>URL</th>
              <th>Type</th>
              <th>Status</th>
              <th>Fetched</th>
              <th>Extraction</th>
              <th>Services</th>
            </tr>
          </thead>
          <tbody>
            {sources.map((s) => (
              <tr key={s.id}>
                <td>
                  <a href={s.source_url} target="_blank" rel="noreferrer">
                    {s.source_url}
                  </a>
                </td>
                <td>{s.document_type}</td>
                <td>
                  <span className={`pill ${s.status}`}>{s.status}</span>
                </td>
                <td>{new Date(s.fetched_at).toLocaleDateString()}</td>
                <td>{s.extraction_method ?? "—"}</td>
                <td>{s.supported_services.join(", ") || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div className="card">
        <h3>Add a source (dashboard-only)</h3>
        <form onSubmit={handleAdd}>
          <div className="form-row">
            <label htmlFor="source-url">URL</label>
            <input
              id="source-url"
              type="url"
              required
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://immigration.gov.lk/..."
            />
          </div>
          <div className="form-row">
            <label htmlFor="source-type">Type</label>
            <select id="source-type" value={docType} onChange={(e) => setDocType(e.target.value as "html" | "pdf")}>
              <option value="html">Web page</option>
              <option value="pdf">PDF</option>
            </select>
          </div>
          {addError && <p className="error">{addError}</p>}
          <button type="submit" disabled={submitting}>
            Record intent
          </button>
        </form>
        {addedNote && <p className="note">{addedNote}</p>}
      </div>
    </div>
  );
}

import { useCallback, useEffect, useState } from "react";

import ContextSelector from "../components/ContextSelector.jsx";
import CsvImportPanel from "../components/CsvImportPanel.jsx";
import DiagnosticForm from "../components/DiagnosticForm.jsx";
import DiagnosticsTable from "../components/DiagnosticsTable.jsx";
import TopBar from "../components/TopBar.jsx";
import {
  ApiError,
  createDiagnostic,
  deleteDiagnostic,
  downloadImportTemplate,
  exportDiagnosticsCsv,
  getFamilies,
  getPhases,
  importDiagnosticsCsv,
  listDiagnostics,
  updateDiagnostic,
} from "../services/api.js";
import { saveBlob } from "../utils/saveFile.js";

// Waits a moment after the last keystroke, so typing a word sends one request instead of one per letter.
const SEARCH_DELAY_MS = 300;

/**
 * Expert screen: browse, create, edit and delete diagnostics, import and export CSV.
 * Hiding it from operators is only a convenience: the backend checks the role on every request.
 *
 * @param {{ user: { username: string, role: string }, onLogout: () => void }} props
 */
export default function KnowledgeBasePage({ user, onLogout }) {
  const [families, setFamilies] = useState([]);
  const [phasesByFamily, setPhasesByFamily] = useState({});
  const [filters, setFilters] = useState({ familyId: null, cyclePhaseId: null, search: "" });
  const [diagnostics, setDiagnostics] = useState([]);
  // null = form closed, {} = new diagnostic, a diagnostic = editing it.
  const [editing, setEditing] = useState(null);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState(null);
  const [error, setError] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);

  const reload = useCallback(() => setReloadKey((key) => key + 1), []);

  // Wraps an API call: an expired session goes back to login, any other error is rethrown to the caller.
  const guarded = useCallback(
    (call) =>
      async (...args) => {
        try {
          return await call(...args);
        } catch (err) {
          if (err instanceof ApiError && err.status === 401) {
            onLogout();
          }
          throw err;
        }
      },
    [onLogout],
  );

  useEffect(() => {
    let ignore = false;
    async function loadCatalog() {
      try {
        const loadedFamilies = await getFamilies();
        const phaseLists = await Promise.all(loadedFamilies.map((family) => getPhases(family.id)));
        if (!ignore) {
          setFamilies(loadedFamilies);
          setPhasesByFamily(Object.fromEntries(loadedFamilies.map((family, index) => [family.id, phaseLists[index]])));
        }
      } catch (err) {
        if (!ignore) {
          setError(err.message);
        }
      }
    }
    guarded(loadCatalog)().catch(() => {});
    return () => {
      ignore = true;
    };
  }, [guarded]);

  useEffect(() => {
    let ignore = false;
    const timer = setTimeout(() => {
      guarded(listDiagnostics)(filters)
        .then((rows) => {
          if (!ignore) {
            setDiagnostics(rows);
            setError(null);
          }
        })
        .catch((err) => {
          if (!ignore) {
            setError(err.message);
          }
        });
    }, SEARCH_DELAY_MS);
    return () => {
      ignore = true;
      clearTimeout(timer);
    };
  }, [filters, reloadKey, guarded]);

  function openForm(diagnostic) {
    setFormError(null);
    setEditing(diagnostic);
  }

  async function handleSave(values) {
    setSaving(true);
    setFormError(null);
    try {
      if (editing.id) {
        await guarded(updateDiagnostic)(editing.id, values);
      } else {
        await guarded(createDiagnostic)(values);
      }
      setEditing(null);
      reload();
    } catch (err) {
      setFormError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(diagnostic) {
    // window.confirm is enough for a PoC: a custom dialog would add a component without new behaviour.
    const confirmed = window.confirm(
      `Eliminare la diagnosi ${diagnostic.id} «${diagnostic.symptom_description}»? L'operazione non si può annullare.`,
    );
    if (!confirmed) {
      return;
    }
    try {
      await guarded(deleteDiagnostic)(diagnostic.id);
      reload();
    } catch (err) {
      setError(err.message);
    }
  }

  async function download(call) {
    const { blob, filename } = await guarded(call)();
    saveBlob(blob, filename);
  }

  async function importFile(file) {
    const report = await guarded(importDiagnosticsCsv)(file, { dryRun: false });
    reload();
    return report;
  }

  return (
    <div className="kb-page">
      <TopBar user={user} onLogout={onLogout} />

      <main className="kb-content">
        <section className="card">
          <div className="section-header">
            <h2>Diagnosi</h2>
            <button type="button" onClick={() => openForm({})}>
              Nuova diagnosi
            </button>
          </div>

          {editing && (
            <DiagnosticForm
              key={editing.id ?? "new"}
              initial={editing}
              families={families}
              phasesByFamily={phasesByFamily}
              saving={saving}
              error={formError}
              onSubmit={handleSave}
              onCancel={() => setEditing(null)}
            />
          )}

          <div className="filters">
            <ContextSelector
              families={families}
              phases={filters.familyId === null ? [] : (phasesByFamily[filters.familyId] ?? [])}
              familyId={filters.familyId}
              phaseId={filters.cyclePhaseId}
              onFamilyChange={(id) => setFilters((current) => ({ ...current, familyId: id, cyclePhaseId: null }))}
              onPhaseChange={(id) => setFilters((current) => ({ ...current, cyclePhaseId: id }))}
              familyLabel="Filtra per famiglia"
              phaseLabel="Filtra per fase"
              familyPlaceholder="Tutte"
              phasePlaceholder="Tutte"
            />
            <label>
              Cerca
              <input
                type="search"
                maxLength={100}
                value={filters.search}
                placeholder="Sintomo, componente, causa..."
                onChange={(event) => setFilters((current) => ({ ...current, search: event.target.value }))}
              />
            </label>
          </div>

          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          <DiagnosticsTable diagnostics={diagnostics} onEdit={openForm} onDelete={handleDelete} />
        </section>

        <CsvImportPanel
          families={families}
          phasesByFamily={phasesByFamily}
          onDownloadTemplate={() => download(downloadImportTemplate)}
          onExport={() => download(exportDiagnosticsCsv)}
          onCheck={(file) => guarded(importDiagnosticsCsv)(file, { dryRun: true })}
          onImport={importFile}
        />
      </main>
    </div>
  );
}

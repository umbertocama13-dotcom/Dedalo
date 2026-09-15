import { useState } from "react";

import CsvGuide from "./CsvGuide.jsx";

/**
 * CSV panel: guide, downloads, check of a file (preview) and import.
 * "Importa" is enabled only after a check without errors on the same file.
 *
 * @param {{
 *   families: Array<object>,
 *   phasesByFamily: Record<number, Array<object>>,
 *   onDownloadTemplate: () => Promise<void>,
 *   onExport: () => Promise<void>,
 *   onCheck: (file: File) => Promise<object>,
 *   onImport: (file: File) => Promise<object>,
 * }} props
 */
export default function CsvImportPanel({ families, phasesByFamily, onDownloadTemplate, onExport, onCheck, onImport }) {
  const [file, setFile] = useState(null);
  const [report, setReport] = useState(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(null);

  async function run(action) {
    setBusy(true);
    setMessage(null);
    try {
      await action();
    } catch (error) {
      // An import rejected for errors carries its report: show the errors, not only a generic message.
      if (Array.isArray(error.detail?.errors)) {
        setReport(error.detail);
      }
      setMessage({ type: "error", text: error.message });
    } finally {
      setBusy(false);
    }
  }

  function handleFileChange(event) {
    setFile(event.target.files[0] ?? null);
    setReport(null);
    setMessage(null);
  }

  async function check() {
    setReport(await onCheck(file));
  }

  async function importFile() {
    const result = await onImport(file);
    setReport(result);
    setMessage({
      type: "success",
      text: `Import completato: ${result.to_create} righe aggiunte, ${result.to_update} modificate.`,
    });
  }

  const checkedWithoutErrors = report !== null && !report.applied && report.errors.length === 0;
  const hasChanges = checkedWithoutErrors && report.to_create + report.to_update > 0;

  return (
    <section className="card csv-panel">
      <h2>Import ed export CSV</h2>
      <CsvGuide families={families} phasesByFamily={phasesByFamily} />

      <div className="csv-actions">
        <button type="button" className="secondary" disabled={busy} onClick={() => run(onDownloadTemplate)}>
          Scarica modello
        </button>
        <button type="button" className="secondary" disabled={busy} onClick={() => run(onExport)}>
          Esporta dati attuali
        </button>
      </div>

      <label>
        File CSV da importare
        <input type="file" accept=".csv,text/csv" onChange={handleFileChange} disabled={busy} />
      </label>
      <div className="csv-actions">
        <button type="button" disabled={!file || busy} onClick={() => run(check)}>
          Controlla file
        </button>
        <button type="button" disabled={!hasChanges || busy} onClick={() => run(importFile)}>
          Importa
        </button>
      </div>

      {message && (
        <p className={message.type} role={message.type === "error" ? "alert" : "status"}>
          {message.text}
        </p>
      )}
      {report && <ImportReport report={report} />}
    </section>
  );
}

function ImportReport({ report }) {
  return (
    <div className="import-report">
      <p>
        {report.applied ? "Salvato" : "Anteprima, nulla è stato salvato"}: <strong>{report.to_create}</strong> righe da
        aggiungere, <strong>{report.to_update}</strong> da modificare, <strong>{report.unchanged}</strong> invariate.
      </p>
      {report.errors.length > 0 && (
        <>
          <p className="error">
            {report.errors.length === 1 ? "1 errore" : `${report.errors.length} errori`}: correggi il file e controllalo di
            nuovo.
          </p>
          <ul className="report-errors">
            {report.errors.map((error) => (
              <li key={`${error.line}-${error.column}-${error.message}`}>
                Riga {error.line}
                {error.column && (
                  <>
                    , <code>{error.column}</code>
                  </>
                )}
                : {error.message}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

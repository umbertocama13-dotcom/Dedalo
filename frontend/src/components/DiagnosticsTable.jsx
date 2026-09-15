function scopeLabel(diagnostic) {
  if (diagnostic.family_id === null) {
    return "Tutte le famiglie";
  }
  if (diagnostic.cycle_phase_id === null) {
    return diagnostic.family_name;
  }
  return `${diagnostic.family_name} · fase ${diagnostic.phase_number} ${diagnostic.phase_name}`;
}

/**
 * Table of diagnostics with edit and delete actions.
 *
 * @param {{ diagnostics: Array<object>, onEdit: (diagnostic: object) => void, onDelete: (diagnostic: object) => void }} props
 */
export default function DiagnosticsTable({ diagnostics, onEdit, onDelete }) {
  if (diagnostics.length === 0) {
    return <p className="hint">Nessuna diagnosi corrisponde ai filtri.</p>;
  }

  return (
    <div className="table-wrapper">
      <table className="kb-table">
        <thead>
          <tr>
            <th>Id</th>
            <th>Ambito</th>
            <th>Sintomo</th>
            <th>Componente</th>
            <th>Causa</th>
            <th>Soluzione</th>
            <th>
              <span className="visually-hidden">Azioni</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {diagnostics.map((diagnostic) => (
            <tr key={diagnostic.id}>
              <td>{diagnostic.id}</td>
              <td>{scopeLabel(diagnostic)}</td>
              <td>{diagnostic.symptom_description}</td>
              <td>{diagnostic.affected_component}</td>
              <td className="long-text">{diagnostic.probable_cause}</td>
              <td className="long-text">{diagnostic.recommended_solution}</td>
              <td className="actions">
                <button type="button" className="secondary" onClick={() => onEdit(diagnostic)}>
                  Modifica
                </button>
                <button type="button" className="danger" onClick={() => onDelete(diagnostic)}>
                  Elimina
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

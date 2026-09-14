// <select> values are always strings: convert back to numeric ids (or null for "not selected").
function toId(value) {
  return value === "" ? null : Number(value);
}

/**
 * Product family and cycle phase pickers that define the diagnosis context.
 *
 * @param {{
 *   families: Array<{ id: number, family_name: string }>,
 *   phases: Array<{ id: number, phase_number: number, phase_name: string }>,
 *   familyId: number | null,
 *   phaseId: number | null,
 *   onFamilyChange: (id: number | null) => void,
 *   onPhaseChange: (id: number | null) => void,
 * }} props
 */
export default function ContextSelector({ families, phases, familyId, phaseId, onFamilyChange, onPhaseChange }) {
  return (
    <div className="context-selector">
      <label>
        Famiglia di prodotto
        <select value={familyId ?? ""} onChange={(event) => onFamilyChange(toId(event.target.value))}>
          <option value="">Seleziona...</option>
          {families.map((family) => (
            <option key={family.id} value={family.id}>
              {family.family_name}
            </option>
          ))}
        </select>
      </label>

      <label>
        Fase del ciclo
        <select
          value={phaseId ?? ""}
          onChange={(event) => onPhaseChange(toId(event.target.value))}
          disabled={familyId === null}
        >
          <option value="">Seleziona...</option>
          {phases.map((phase) => (
            <option key={phase.id} value={phase.id}>
              {phase.phase_number}. {phase.phase_name}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}

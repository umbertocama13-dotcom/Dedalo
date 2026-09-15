import { useState } from "react";

import ContextSelector from "./ContextSelector.jsx";

// Same limits as the backend (DiagnosticIn).
const MAX_SYMPTOM_LENGTH = 500;
const MAX_COMPONENT_LENGTH = 150;
const MAX_TEXT_LENGTH = 10000;

function scopeHint(familyId, phaseId) {
  if (familyId === null) {
    return "La diagnosi verrà proposta per ogni famiglia di prodotto.";
  }
  if (phaseId === null) {
    return "La diagnosi verrà proposta per tutta la famiglia, qualunque sia la fase.";
  }
  return "La diagnosi verrà proposta in questa fase, oppure quando l'operatore non indica la fase.";
}

/**
 * Create or edit form of a diagnostic. It only collects input: the page decides what saving means.
 *
 * @param {{
 *   initial: object,
 *   families: Array<object>,
 *   phasesByFamily: Record<number, Array<object>>,
 *   saving: boolean,
 *   error: string | null,
 *   onSubmit: (diagnostic: object) => void,
 *   onCancel: () => void,
 * }} props
 */
export default function DiagnosticForm({ initial, families, phasesByFamily, saving, error, onSubmit, onCancel }) {
  const [values, setValues] = useState({
    symptom_description: initial.symptom_description ?? "",
    affected_component: initial.affected_component ?? "",
    probable_cause: initial.probable_cause ?? "",
    recommended_solution: initial.recommended_solution ?? "",
    family_id: initial.family_id ?? null,
    cycle_phase_id: initial.cycle_phase_id ?? null,
  });

  function setField(field, value) {
    setValues((current) => ({ ...current, [field]: value }));
  }

  function handleSubmit(event) {
    event.preventDefault();
    onSubmit(values);
  }

  return (
    <form className="kb-form" onSubmit={handleSubmit}>
      <h3>{initial.id ? `Modifica diagnosi ${initial.id}` : "Nuova diagnosi"}</h3>

      <label>
        Sintomo
        <textarea
          required
          rows={2}
          maxLength={MAX_SYMPTOM_LENGTH}
          value={values.symptom_description}
          onChange={(event) => setField("symptom_description", event.target.value)}
        />
      </label>
      <label>
        Componente
        <input
          required
          maxLength={MAX_COMPONENT_LENGTH}
          value={values.affected_component}
          onChange={(event) => setField("affected_component", event.target.value)}
        />
      </label>
      <label>
        Causa probabile
        <textarea
          required
          rows={3}
          maxLength={MAX_TEXT_LENGTH}
          value={values.probable_cause}
          onChange={(event) => setField("probable_cause", event.target.value)}
        />
      </label>
      <label>
        Soluzione consigliata
        <textarea
          required
          rows={3}
          maxLength={MAX_TEXT_LENGTH}
          value={values.recommended_solution}
          onChange={(event) => setField("recommended_solution", event.target.value)}
        />
      </label>

      <ContextSelector
        families={families}
        phases={values.family_id === null ? [] : (phasesByFamily[values.family_id] ?? [])}
        familyId={values.family_id}
        phaseId={values.cycle_phase_id}
        onFamilyChange={(id) => setValues((current) => ({ ...current, family_id: id, cycle_phase_id: null }))}
        onPhaseChange={(id) => setField("cycle_phase_id", id)}
        familyLabel="Famiglia"
        phaseLabel="Fase"
        familyPlaceholder="Tutte le famiglie"
        phasePlaceholder="Tutta la famiglia"
      />
      <p className="hint">{scopeHint(values.family_id, values.cycle_phase_id)}</p>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <div className="form-actions">
        <button type="submit" disabled={saving}>
          {saving ? "Salvataggio..." : "Salva"}
        </button>
        <button type="button" className="secondary" onClick={onCancel} disabled={saving}>
          Annulla
        </button>
      </div>
    </form>
  );
}

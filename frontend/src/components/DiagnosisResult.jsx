import ChoiceOptions from "./ChoiceOptions.jsx";

const SCOPE_LABELS = { generic: "Tutte le famiglie", family: "Tutta la famiglia" };

// Percentages are whole numbers: 0 means "less than 1%", not "impossible".
function formatProbability(probability) {
  return probability === 0 ? "<1%" : `${probability}%`;
}

/**
 * Renders one answer of the diagnosis conversation, choosing the view from `response.status`.
 *
 * @param {{ response: object, interactive: boolean, onSelect: (label: string, excludedIds: number[]) => void }} props
 */
export default function DiagnosisResult({ response, interactive, onSelect }) {
  switch (response.status) {
    case "hypotheses":
      return <HypothesesResult response={response} interactive={interactive} onSelect={onSelect} />;
    case "no_match":
      return (
        <div className="result no-match">
          <strong>Nessun dato disponibile</strong>
          <p>
            La knowledge base non contiene una diagnosi compatibile con questo sintomo per il contesto selezionato.
            Nessuna procedura viene suggerita: contatta un tecnico specializzato.
          </p>
          <ModeNote response={response} />
        </div>
      );
    default:
      // An unknown status must never be displayed as a diagnosis.
      return (
        <div className="result unknown">
          Risposta non riconosciuta (stato: {response.status}). Aggiorna l'applicazione.
        </div>
      );
  }
}

function HypothesesResult({ response, interactive, onSelect }) {
  const { hypotheses, confidence, follow_up: followUp, unknown_probability: unknownProbability } = response;

  return (
    <div className="result">
      {confidence === "low" ? (
        <div className="uncertain">
          <strong>Nessuna corrispondenza sicura</strong>
          <p>
            Queste ipotesi sono solo simili al sintomo descritto: verificale con attenzione oppure descrivi il sintomo
            con più dettagli.
          </p>
        </div>
      ) : (
        <strong>
          {hypotheses.length === 1 ? "1 ipotesi trovata" : `${hypotheses.length} ipotesi, in ordine di probabilità stimata`}
        </strong>
      )}

      <ol className="hypotheses">
        {hypotheses.map((hypothesis) => (
          <li key={hypothesis.diagnostic_id} className="hypothesis">
            <div className="hypothesis-header">
              <span className="component">{hypothesis.affected_component}</span>
              <span className={`badge scope-${hypothesis.scope}`}>
                {hypothesis.scope === "phase"
                  ? `Fase ${hypothesis.phase_number} · ${hypothesis.phase_name}`
                  : SCOPE_LABELS[hypothesis.scope]}
              </span>
            </div>
            <ProbabilityBar value={hypothesis.probability} />
            <p className="registered-symptom">Sintomo registrato: {hypothesis.symptom_description}</p>
            <p>
              <strong>Causa:</strong> {hypothesis.cause}
            </p>
            <p>
              <strong>Soluzione:</strong> {hypothesis.solution}
            </p>
          </li>
        ))}
      </ol>

      {typeof unknownProbability === "number" && (
        <div className="unknown-share">
          <span>Nessuna di queste ipotesi</span>
          <ProbabilityBar value={unknownProbability} muted />
        </div>
      )}
      <p className="hint">
        Probabilità stimate dalla somiglianza con i sintomi registrati, compresa la possibilità che la causa non sia tra
        queste ipotesi.
      </p>

      {followUp && <ChoiceOptions followUp={followUp} disabled={!interactive} onSelect={onSelect} />}
      <ModeNote response={response} />
    </div>
  );
}

function ProbabilityBar({ value, muted = false }) {
  return (
    <div className="probability" role="img" aria-label={`Probabilità stimata ${formatProbability(value)}`}>
      <div className="probability-track">
        <div className={`probability-fill${muted ? " muted" : ""}`} style={{ width: `${value}%` }} />
      </div>
      <span className="probability-value">{formatProbability(value)}</span>
    </div>
  );
}

function ModeNote({ response }) {
  if (response.mode === "llm") {
    return <p className="hint">Conversazione guidata dall'assistente AI: cause e soluzioni vengono sempre dalla knowledge base.</p>;
  }
  if (response.ai_fallback) {
    return <p className="hint">Assistente AI non disponibile: risposta calcolata in modalità offline.</p>;
  }
  return <p className="hint">Modalità offline: nessun testo lascia la macchina.</p>;
}

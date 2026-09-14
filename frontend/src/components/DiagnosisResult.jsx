/**
 * Renders a diagnosis response, choosing the view from `response.status`.
 *
 * @param {{ response: { status: string, matched_on: string | null, matched_text: string | null, hypotheses: Array<object> } }} props
 */
export default function DiagnosisResult({ response }) {
  switch (response.status) {
    case "match":
      return <MatchResult response={response} />;
    case "no_match":
      return (
        <div className="result no-match">
          <strong>Nessun dato disponibile</strong>
          <p>
            La knowledge base non contiene una diagnosi per questo sintomo nella famiglia e nella fase selezionate.
            Nessuna procedura viene suggerita: contatta un tecnico specializzato.
          </p>
        </div>
      );
    default:
      // An unknown status (e.g. a future "disambiguation") must never be displayed as a diagnosis.
      return (
        <div className="result unknown">
          Risposta non riconosciuta (stato: {response.status}). Aggiorna l'applicazione.
        </div>
      );
  }
}

function MatchResult({ response }) {
  const { hypotheses, matched_on: matchedOn, matched_text: matchedText } = response;
  const title =
    hypotheses.length === 1 ? "1 diagnosi trovata" : `${hypotheses.length} ipotesi trovate, in ordine di somiglianza`;

  return (
    <div className="result match">
      <strong>{title}</strong>
      {matchedOn === "ai_normalized" && <p className="hint">Sintomo interpretato come: «{matchedText}»</p>}

      <ol className="hypotheses">
        {hypotheses.map((hypothesis) => (
          <li key={hypothesis.base_diagnostic_id} className="hypothesis">
            <div className="hypothesis-header">
              <span className="component">{hypothesis.affected_component}</span>
              {hypothesis.source === "exception" && <span className="badge">Specifica per questa fase</span>}
              <span className="score">somiglianza {Math.round(hypothesis.score)}%</span>
            </div>
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
    </div>
  );
}

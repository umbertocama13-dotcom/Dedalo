/**
 * Follow-up of an answer: buttons for a choice question, or a model question to answer in the chat box.
 *
 * Choosing an option excludes the hypotheses of every other option; "Nessuna di queste"
 * excludes all of them. The page sends the exclusions with the next request.
 *
 * @param {{
 *   followUp: { type: "choice" | "question", question: string, options: Array<{ label: string, diagnostic_ids: number[] }> },
 *   disabled: boolean,
 *   onSelect: (label: string, excludedIds: number[]) => void,
 * }} props
 */
export default function ChoiceOptions({ followUp, disabled, onSelect }) {
  if (followUp.type === "question") {
    return (
      <div className="follow-up">
        <p className="assistant-question">{followUp.question}</p>
        {!disabled && <p className="hint">Rispondi nella casella qui sotto.</p>}
      </div>
    );
  }

  const allIds = followUp.options.flatMap((option) => option.diagnostic_ids);
  return (
    <div className="follow-up">
      <p className="assistant-question">{followUp.question}</p>
      <div className="choices">
        {followUp.options.map((option) => (
          <button
            key={option.label}
            type="button"
            className="choice"
            disabled={disabled}
            onClick={() => onSelect(option.label, allIds.filter((id) => !option.diagnostic_ids.includes(id)))}
          >
            {option.label}
          </button>
        ))}
        <button type="button" className="choice none" disabled={disabled} onClick={() => onSelect("Nessuna di queste", allIds)}>
          Nessuna di queste
        </button>
      </div>
    </div>
  );
}

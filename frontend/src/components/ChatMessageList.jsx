import { useEffect, useRef } from "react";

import DiagnosisResult from "./DiagnosisResult.jsx";

/**
 * Conversation history: operator messages, answers and errors.
 *
 * Only the latest answer is interactive: choosing an option in an older one would mix two turns.
 *
 * @param {{
 *   messages: Array<{ id: number, role: "operator" | "assistant" | "error", text?: string, contextLabel?: string, response?: object }>,
 *   loading: boolean,
 *   onSelect: (label: string, excludedIds: number[]) => void,
 * }} props
 */
export default function ChatMessageList({ messages, loading, onSelect }) {
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  if (messages.length === 0 && !loading) {
    return (
      <div className="messages empty">
        Seleziona la famiglia di prodotto (e la fase, se la conosci), poi descrivi il sintomo con parole tue.
      </div>
    );
  }

  const latestAnswerId = messages.findLast((message) => message.role === "assistant")?.id;

  return (
    <div className="messages">
      {messages.map((message) => (
        <div key={message.id} className={`message ${message.role}`}>
          {message.role === "operator" && (
            <>
              {message.contextLabel && <span className="context-label">{message.contextLabel}</span>}
              <p>{message.text}</p>
            </>
          )}
          {message.role === "assistant" && (
            <DiagnosisResult
              response={message.response}
              interactive={!loading && message.id === latestAnswerId}
              onSelect={onSelect}
            />
          )}
          {message.role === "error" && <p role="alert">{message.text}</p>}
        </div>
      ))}
      {loading && <div className="message assistant pending">Ricerca nella knowledge base...</div>}
      <div ref={endRef} />
    </div>
  );
}

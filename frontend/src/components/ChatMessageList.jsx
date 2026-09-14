import { useEffect, useRef } from "react";

import DiagnosisResult from "./DiagnosisResult.jsx";

/**
 * Conversation history: operator messages, diagnosis results and errors.
 *
 * @param {{ messages: Array<{ id: number, role: "operator" | "assistant" | "error", text?: string, contextLabel?: string, response?: object }>, loading: boolean }} props
 */
export default function ChatMessageList({ messages, loading }) {
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  if (messages.length === 0 && !loading) {
    return <div className="messages empty">Seleziona famiglia e fase, poi descrivi il sintomo osservato.</div>;
  }

  return (
    <div className="messages">
      {messages.map((message) => (
        <div key={message.id} className={`message ${message.role}`}>
          {message.role === "operator" && (
            <>
              <span className="context-label">{message.contextLabel}</span>
              <p>{message.text}</p>
            </>
          )}
          {message.role === "assistant" && <DiagnosisResult response={message.response} />}
          {message.role === "error" && <p role="alert">{message.text}</p>}
        </div>
      ))}
      {loading && <div className="message assistant pending">Ricerca nella knowledge base...</div>}
      <div ref={endRef} />
    </div>
  );
}

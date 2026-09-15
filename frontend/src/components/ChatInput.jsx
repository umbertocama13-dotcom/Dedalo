import { useState } from "react";

// Same limit as the backend (ChatMessage.content).
const MAX_SYMPTOM_LENGTH = 1000;

/**
 * Text box where the operator describes the symptom.
 *
 * @param {{ onSend: (text: string) => void, disabled: boolean, placeholder: string }} props
 */
export default function ChatInput({ onSend, disabled, placeholder }) {
  const [text, setText] = useState("");
  const trimmed = text.trim();

  function send() {
    if (!trimmed || disabled) {
      return;
    }
    onSend(trimmed);
    setText("");
  }

  function handleKeyDown(event) {
    // Enter sends, Shift+Enter inserts a new line.
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      send();
    }
  }

  return (
    <form
      className="chat-input"
      onSubmit={(event) => {
        event.preventDefault();
        send();
      }}
    >
      <textarea
        value={text}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        maxLength={MAX_SYMPTOM_LENGTH}
        rows={2}
        disabled={disabled}
      />
      <button type="submit" disabled={disabled || !trimmed}>
        Invia
      </button>
    </form>
  );
}

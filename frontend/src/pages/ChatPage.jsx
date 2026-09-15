import { useCallback, useEffect, useRef, useState } from "react";

import ChatInput from "../components/ChatInput.jsx";
import ChatMessageList from "../components/ChatMessageList.jsx";
import ContextSelector from "../components/ContextSelector.jsx";
import TopBar from "../components/TopBar.jsx";
import { ApiError, diagnose, getFamilies, getPhases } from "../services/api.js";

// Same limit as the backend (DiagnosisRequest.messages).
const MAX_MESSAGES = 20;

/**
 * Diagnosis conversation: choose the family (and the phase if known), describe the symptom,
 * read the hypotheses and answer the follow-up questions.
 *
 * The backend keeps no conversation state, so this page owns it: the messages sent to the
 * API and the hypotheses excluded by the operator's choices.
 *
 * @param {{ user: { username: string, role: string }, onLogout: () => void }} props
 */
export default function ChatPage({ user, onLogout }) {
  const [families, setFamilies] = useState([]);
  const [phases, setPhases] = useState([]);
  const [familyId, setFamilyId] = useState(null);
  const [phaseId, setPhaseId] = useState(null);
  // Displayed messages (operator bubbles, answers, errors).
  const [messages, setMessages] = useState([]);
  // Messages sent to the API: operator texts and model questions only.
  const [history, setHistory] = useState([]);
  const [excludedIds, setExcludedIds] = useState([]);
  const [loading, setLoading] = useState(false);
  const nextMessageId = useRef(0);

  const addMessage = useCallback((message) => {
    nextMessageId.current += 1;
    const id = nextMessageId.current;
    setMessages((previous) => [...previous, { id, ...message }]);
  }, []);

  const handleApiError = useCallback(
    (error) => {
      // Expired or revoked session: back to the login screen.
      if (error instanceof ApiError && error.status === 401) {
        onLogout();
        return;
      }
      addMessage({ role: "error", text: error.message });
    },
    [addMessage, onLogout],
  );

  const resetConversation = useCallback(() => {
    setMessages([]);
    setHistory([]);
    setExcludedIds([]);
  }, []);

  useEffect(() => {
    getFamilies().then(setFamilies).catch(handleApiError);
  }, [handleApiError]);

  useEffect(() => {
    if (familyId === null) {
      return undefined;
    }
    let ignore = false;
    getPhases(familyId)
      .then((data) => {
        // Drop late answers if the family changed again before this request finished.
        if (!ignore) {
          setPhases(data);
        }
      })
      .catch(handleApiError);
    return () => {
      ignore = true;
    };
  }, [familyId, handleApiError]);

  // A different context is a different conversation: previous hypotheses would not apply.
  function handleFamilyChange(id) {
    setFamilyId(id);
    setPhaseId(null);
    setPhases([]);
    resetConversation();
  }

  function handlePhaseChange(id) {
    setPhaseId(id);
    resetConversation();
  }

  function contextLabel() {
    const family = families.find((item) => item.id === familyId);
    const phase = phases.find((item) => item.id === phaseId);
    return `${family.family_name} · ${phase ? `fase ${phase.phase_number} ${phase.phase_name}` : "fase non indicata"}`;
  }

  async function runTurn(nextHistory, nextExcludedIds) {
    setLoading(true);
    try {
      const response = await diagnose({
        familyId,
        cyclePhaseId: phaseId,
        messages: nextHistory,
        excludedIds: nextExcludedIds,
      });
      addMessage({ role: "assistant", response });
      // A model question joins the history, so the model knows what it already asked.
      if (response.follow_up?.type === "question") {
        setHistory([...nextHistory, { role: "assistant", content: response.follow_up.question }]);
      }
    } catch (error) {
      handleApiError(error);
    } finally {
      setLoading(false);
    }
  }

  function handleSend(text) {
    addMessage({ role: "operator", text, contextLabel: history.length === 0 ? contextLabel() : undefined });
    const nextHistory = [...history, { role: "operator", content: text }];
    setHistory(nextHistory);
    runTurn(nextHistory, excludedIds);
  }

  function handleSelect(label, idsToExclude) {
    addMessage({ role: "operator", text: `Scelta: ${label}` });
    const nextExcludedIds = [...new Set([...excludedIds, ...idsToExclude])];
    setExcludedIds(nextExcludedIds);
    runTurn(history, nextExcludedIds);
  }

  const contextReady = familyId !== null;
  const conversationFull = history.length >= MAX_MESSAGES;
  let placeholder = "Descrivi il sintomo osservato...";
  if (!contextReady) {
    placeholder = "Seleziona prima la famiglia di prodotto";
  } else if (conversationFull) {
    placeholder = "Conversazione troppo lunga: avviane una nuova";
  } else if (history.length > 0) {
    placeholder = "Rispondi o aggiungi dettagli sul sintomo...";
  }

  return (
    <div className="chat-page">
      <TopBar user={user} onLogout={onLogout} />

      <ContextSelector
        families={families}
        phases={phases}
        familyId={familyId}
        phaseId={phaseId}
        onFamilyChange={handleFamilyChange}
        onPhaseChange={handlePhaseChange}
      />

      {messages.length > 0 && (
        <div className="conversation-actions">
          <button type="button" className="secondary" onClick={resetConversation} disabled={loading}>
            Nuova conversazione
          </button>
        </div>
      )}

      <ChatMessageList messages={messages} loading={loading} onSelect={handleSelect} />

      <ChatInput onSend={handleSend} disabled={!contextReady || loading || conversationFull} placeholder={placeholder} />
    </div>
  );
}

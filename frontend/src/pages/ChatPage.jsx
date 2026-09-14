import { useCallback, useEffect, useRef, useState } from "react";

import ChatInput from "../components/ChatInput.jsx";
import ChatMessageList from "../components/ChatMessageList.jsx";
import ContextSelector from "../components/ContextSelector.jsx";
import { ApiError, diagnose, getFamilies, getPhases } from "../services/api.js";

const ROLE_LABELS = { expert: "esperto", operator: "operatore" };

/**
 * Chat screen: choose family and phase, describe a symptom, read the diagnosis.
 *
 * @param {{ user: { username: string, role: string }, onLogout: () => void }} props
 */
export default function ChatPage({ user, onLogout }) {
  const [families, setFamilies] = useState([]);
  const [phases, setPhases] = useState([]);
  const [familyId, setFamilyId] = useState(null);
  const [phaseId, setPhaseId] = useState(null);
  const [messages, setMessages] = useState([]);
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

  function handleFamilyChange(id) {
    setFamilyId(id);
    setPhaseId(null);
    setPhases([]);
  }

  async function handleSend(symptom) {
    const family = families.find((item) => item.id === familyId);
    const phase = phases.find((item) => item.id === phaseId);
    addMessage({
      role: "operator",
      text: symptom,
      contextLabel: `${family.family_name} · fase ${phase.phase_number} ${phase.phase_name}`,
    });

    setLoading(true);
    try {
      addMessage({ role: "assistant", response: await diagnose(symptom, familyId, phaseId) });
    } catch (error) {
      handleApiError(error);
    } finally {
      setLoading(false);
    }
  }

  const contextReady = familyId !== null && phaseId !== null;

  return (
    <div className="chat-page">
      <header className="topbar">
        <span className="brand">Dedalo</span>
        <span className="user">
          {user.username} ({ROLE_LABELS[user.role] ?? user.role})
        </span>
        <button type="button" className="secondary" onClick={onLogout}>
          Esci
        </button>
      </header>

      <ContextSelector
        families={families}
        phases={phases}
        familyId={familyId}
        phaseId={phaseId}
        onFamilyChange={handleFamilyChange}
        onPhaseChange={setPhaseId}
      />

      <ChatMessageList messages={messages} loading={loading} />

      <ChatInput
        onSend={handleSend}
        disabled={!contextReady || loading}
        placeholder={contextReady ? "Descrivi il sintomo osservato..." : "Seleziona prima famiglia e fase"}
      />
    </div>
  );
}

import { useCallback, useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import ChatPage from "./pages/ChatPage.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import { getCurrentUser, getToken, logout } from "./services/api.js";

/** Routing and session state: decides which page the user can see. */
export default function App() {
  const [user, setUser] = useState(null);
  // A token saved in this tab must be checked with the backend before choosing the page.
  const [checkingSession, setCheckingSession] = useState(() => getToken() !== null);

  useEffect(() => {
    if (getToken() === null) {
      return;
    }
    getCurrentUser()
      .then(setUser)
      .catch(() => logout())
      .finally(() => setCheckingSession(false));
  }, []);

  const handleLogout = useCallback(() => {
    logout();
    setUser(null);
  }, []);

  if (checkingSession) {
    return <p className="loading-page">Verifica della sessione...</p>;
  }

  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/chat" replace /> : <LoginPage onLogin={setUser} />} />
      <Route
        path="/chat"
        element={user ? <ChatPage user={user} onLogout={handleLogout} /> : <Navigate to="/login" replace />}
      />
      <Route path="*" element={<Navigate to={user ? "/chat" : "/login"} replace />} />
    </Routes>
  );
}

import { useCallback, useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import ChatPage from "./pages/ChatPage.jsx";
import KnowledgeBasePage from "./pages/KnowledgeBasePage.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import SetupPage from "./pages/SetupPage.jsx";
import UsersPage from "./pages/UsersPage.jsx";
import { getCurrentUser, getSetupStatus, getToken, logout } from "./services/api.js";

/** Routing and session state: decides which page the user can see. */
export default function App() {
  const [user, setUser] = useState(null);
  // A token saved in this tab must be checked with the backend before choosing the page.
  const [checkingSession, setCheckingSession] = useState(() => getToken() !== null);
  // null while asking the backend whether this is a fresh installation without users.
  const [needsSetup, setNeedsSetup] = useState(null);

  useEffect(() => {
    getSetupStatus()
      .then((status) => setNeedsSetup(status.needs_setup))
      // Backend unreachable: go on to the login page, which shows the connection error.
      .catch(() => setNeedsSetup(false));
  }, []);

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

  const handleSetupDone = useCallback((createdUser) => {
    setNeedsSetup(false);
    setUser(createdUser);
  }, []);

  if (checkingSession || needsSetup === null) {
    return <p className="loading-page">Avvio di Dedalo...</p>;
  }

  if (needsSetup) {
    return (
      <Routes>
        <Route
          path="/setup"
          element={<SetupPage onDone={handleSetupDone} onAlreadyConfigured={() => setNeedsSetup(false)} />}
        />
        <Route path="*" element={<Navigate to="/setup" replace />} />
      </Routes>
    );
  }

  // Hiding expert pages from operators is only a convenience: the backend rejects their requests anyway.
  function expertOnly(element) {
    if (!user) {
      return <Navigate to="/login" replace />;
    }
    return user.role === "expert" ? element : <Navigate to="/chat" replace />;
  }

  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/chat" replace /> : <LoginPage onLogin={setUser} />} />
      <Route
        path="/chat"
        element={user ? <ChatPage user={user} onLogout={handleLogout} /> : <Navigate to="/login" replace />}
      />
      <Route path="/knowledge-base" element={expertOnly(<KnowledgeBasePage user={user} onLogout={handleLogout} />)} />
      <Route path="/users" element={expertOnly(<UsersPage user={user} onLogout={handleLogout} />)} />
      <Route path="*" element={<Navigate to={user ? "/chat" : "/login"} replace />} />
    </Routes>
  );
}

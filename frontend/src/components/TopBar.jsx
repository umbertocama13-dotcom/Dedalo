import { NavLink } from "react-router-dom";

const ROLE_LABELS = { expert: "esperto", operator: "operatore" };

/**
 * Top bar shared by every page: navigation, current user and logout.
 * The knowledge base link is shown only to experts; the backend still checks the role on every request.
 *
 * @param {{ user: { username: string, role: string }, onLogout: () => void }} props
 */
export default function TopBar({ user, onLogout }) {
  return (
    <header className="topbar">
      <span className="brand">Dedalo</span>
      <nav className="nav">
        <NavLink to="/chat">Diagnosi</NavLink>
        {user.role === "expert" && <NavLink to="/knowledge-base">Knowledge base</NavLink>}
        {user.role === "expert" && <NavLink to="/users">Utenti</NavLink>}
      </nav>
      <span className="user">
        {user.username} ({ROLE_LABELS[user.role] ?? user.role})
      </span>
      <button type="button" className="secondary" onClick={onLogout}>
        Esci
      </button>
    </header>
  );
}

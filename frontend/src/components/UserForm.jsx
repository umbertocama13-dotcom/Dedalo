import { useState } from "react";

// Same rules as the backend (UserIn). In a pattern attribute "-" must be escaped inside [...].
const USERNAME_PATTERN = "[A-Za-z0-9._\\-]+";
const MIN_PASSWORD_LENGTH = 8;

/**
 * Form to create a user. It only collects input: the page decides what saving means.
 *
 * @param {{ saving: boolean, error: string | null, onSubmit: (user: { username: string, password: string, role: string }) => void }} props
 */
export default function UserForm({ saving, error, onSubmit }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("operator");

  function handleSubmit(event) {
    event.preventDefault();
    onSubmit({ username, password, role });
  }

  return (
    <form className="kb-form" onSubmit={handleSubmit}>
      <h3>Nuovo utente</h3>
      <div className="user-fields">
        <label>
          Username
          <input
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            required
            minLength={3}
            maxLength={50}
            pattern={USERNAME_PATTERN}
            title="Lettere, numeri, punto, trattino e trattino basso, senza spazi"
            autoComplete="off"
          />
        </label>
        <label>
          Password (almeno {MIN_PASSWORD_LENGTH} caratteri)
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
            minLength={MIN_PASSWORD_LENGTH}
            maxLength={128}
            autoComplete="new-password"
          />
        </label>
        <label>
          Ruolo
          <select value={role} onChange={(event) => setRole(event.target.value)}>
            <option value="operator">Operatore (solo consultazione)</option>
            <option value="expert">Esperto (gestisce knowledge base e utenti)</option>
          </select>
        </label>
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <div className="form-actions">
        <button type="submit" disabled={saving}>
          {saving ? "Creazione..." : "Crea utente"}
        </button>
      </div>
    </form>
  );
}

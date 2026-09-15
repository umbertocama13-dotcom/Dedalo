import { useState } from "react";

import { ApiError, getCurrentUser, login, runSetup } from "../services/api.js";

// Same rules as the backend (SetupIn). In a pattern attribute "-" must be escaped inside [...].
const USERNAME_PATTERN = "[A-Za-z0-9._\\-]+";
const MIN_PASSWORD_LENGTH = 8;

/**
 * First-start screen of a new installation: creates the first expert, then logs in with it.
 *
 * @param {{ onDone: (user: object) => void, onAlreadyConfigured: () => void }} props
 */
export default function SetupPage({ onDone, onAlreadyConfigured }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [loadSample, setLoadSample] = useState(true);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    if (password !== confirmation) {
      setError("Le due password non coincidono.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await runSetup({ username, password, loadSampleDiagnostics: loadSample });
      await login(username, password);
      onDone(await getCurrentUser());
    } catch (err) {
      // Someone completed the setup in the meantime: the normal login page applies.
      if (err instanceof ApiError && err.status === 409) {
        onAlreadyConfigured();
        return;
      }
      setError(err.message);
      setSaving(false);
    }
  }

  return (
    <main className="login-page">
      <form className="card login-form setup-form" onSubmit={handleSubmit}>
        <h1>Benvenuto in Dedalo</h1>
        <p className="subtitle">
          Primo avvio: crea l'account dell'esperto, che gestirà la knowledge base e gli utenti degli operatori.
        </p>

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
            autoComplete="username"
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
          Ripeti la password
          <input
            type="password"
            value={confirmation}
            onChange={(event) => setConfirmation(event.target.value)}
            required
            autoComplete="new-password"
          />
        </label>
        <label className="checkbox">
          <input type="checkbox" checked={loadSample} onChange={(event) => setLoadSample(event.target.checked)} />
          Carica le diagnosi di esempio (utili per provare l'app, si possono modificare o eliminare)
        </label>
        <p className="hint">Conserva la password: non esiste un recupero automatico.</p>

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" disabled={saving}>
          {saving ? "Configurazione in corso..." : "Crea l'esperto e inizia"}
        </button>
      </form>
    </main>
  );
}

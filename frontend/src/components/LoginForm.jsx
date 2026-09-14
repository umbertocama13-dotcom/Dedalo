import { useState } from "react";

/**
 * Username/password form. It only collects input: the page decides what login means.
 *
 * @param {{ onSubmit: (username: string, password: string) => void, error: string | null, loading: boolean }} props
 */
export default function LoginForm({ onSubmit, error, loading }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  function handleSubmit(event) {
    event.preventDefault();
    onSubmit(username, password);
  }

  return (
    <form className="card login-form" onSubmit={handleSubmit}>
      <h1>Dedalo</h1>
      <p className="subtitle">Assistente di troubleshooting guidato</p>

      <label>
        Username
        <input
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          autoComplete="username"
          required
        />
      </label>

      <label>
        Password
        <input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="current-password"
          required
        />
      </label>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      <button type="submit" disabled={loading}>
        {loading ? "Accesso in corso..." : "Accedi"}
      </button>
    </form>
  );
}

import { useState } from "react";

import LoginForm from "../components/LoginForm.jsx";
import { ApiError, getCurrentUser, login } from "../services/api.js";

/**
 * Login screen: authenticates, then hands the user (with role) to the App.
 *
 * @param {{ onLogin: (user: { id: number, username: string, role: string }) => void }} props
 */
export default function LoginPage({ onLogin }) {
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(username, password) {
    setLoading(true);
    setError(null);
    try {
      await login(username, password);
      onLogin(await getCurrentUser());
    } catch (err) {
      const wrongCredentials = err instanceof ApiError && err.status === 400;
      setError(wrongCredentials ? "Username o password non corretti." : err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="login-page">
      <LoginForm onSubmit={handleSubmit} error={error} loading={loading} />
    </main>
  );
}

import { useEffect, useState } from "react";

import TopBar from "../components/TopBar.jsx";
import UserForm from "../components/UserForm.jsx";
import UsersTable from "../components/UsersTable.jsx";
import { useAuthGuard } from "../hooks/useAuthGuard.js";
import { createUser, listUsers } from "../services/api.js";

/**
 * Expert screen: list users and create operator or expert accounts.
 * Hiding it from operators is only a convenience: the backend checks the role on every request.
 *
 * @param {{ user: { username: string, role: string }, onLogout: () => void }} props
 */
export default function UsersPage({ user, onLogout }) {
  const [users, setUsers] = useState([]);
  const [error, setError] = useState(null);
  const [formError, setFormError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);
  // Changing the key remounts the form, which clears its fields after a successful creation.
  const [formKey, setFormKey] = useState(0);
  const guarded = useAuthGuard(onLogout);

  useEffect(() => {
    let ignore = false;
    guarded(listUsers)()
      .then((rows) => {
        if (!ignore) {
          setUsers(rows);
        }
      })
      .catch((err) => {
        if (!ignore) {
          setError(err.message);
        }
      });
    return () => {
      ignore = true;
    };
  }, [guarded, formKey]);

  async function handleCreate(values) {
    setSaving(true);
    setFormError(null);
    setMessage(null);
    try {
      const created = await guarded(createUser)(values);
      setMessage(`Utente «${created.username}» creato: comunicagli username e password.`);
      setFormKey((key) => key + 1);
    } catch (err) {
      setFormError(err.status === 409 ? "Questo username esiste già." : err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="kb-page">
      <TopBar user={user} onLogout={onLogout} />
      <main className="kb-content">
        <section className="card">
          <h2>Utenti</h2>
          <UserForm key={formKey} saving={saving} error={formError} onSubmit={handleCreate} />
          {message && (
            <p className="success" role="status">
              {message}
            </p>
          )}
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          <UsersTable users={users} />
        </section>
      </main>
    </div>
  );
}

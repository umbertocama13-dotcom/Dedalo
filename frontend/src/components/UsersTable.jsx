const ROLE_LABELS = { expert: "Esperto", operator: "Operatore" };

/**
 * Table of the existing users.
 *
 * @param {{ users: Array<{ id: number, username: string, role: string }> }} props
 */
export default function UsersTable({ users }) {
  if (users.length === 0) {
    return <p className="hint">Nessun utente.</p>;
  }

  return (
    <div className="table-wrapper">
      <table className="kb-table">
        <thead>
          <tr>
            <th>Username</th>
            <th>Ruolo</th>
          </tr>
        </thead>
        <tbody>
          {users.map((user) => (
            <tr key={user.id}>
              <td>{user.username}</td>
              <td>{ROLE_LABELS[user.role] ?? user.role}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

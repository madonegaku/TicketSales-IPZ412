import { Meteor } from "meteor/meteor";
import { useState } from "react";
import { ROLE_LABELS, ROLES } from "/imports/api/roles";
import { formatDate } from "../format";
import { messageOf, useCurrentUser, useMethod } from "../hooks";

// Адміністрування: ролі й блокування користувачів. Облікові записи – дані web (ADR-006).
export function AdminPage() {
  const { user: me } = useCurrentUser();
  const { data: users, error, loading, reload } = useMethod("admin.users");
  const [message, setMessage] = useState(null);
  if (loading) return <p className="muted">Завантаження користувачів…</p>;
  if (error) return <p className="error">{error}</p>;

  const run = async (action, success) => {
    setMessage(null);
    try {
      await action();
      setMessage({ ok: true, text: success });
    } catch (problem) {
      setMessage({ ok: false, text: messageOf(problem) });
    }
    reload();
  };

  const toggleRole = (user, role) => {
    const roles = user.roles.includes(role) ? user.roles.filter((r) => r !== role) : [...user.roles, role];
    return run(() => Meteor.callAsync("admin.setRoles", user.id, roles), `Ролі ${user.email} оновлено.`);
  };

  const toggleBlocked = (user) => run(
    () => Meteor.callAsync("admin.setBlocked", user.id, !user.blocked),
    user.blocked ? `${user.email} розблоковано.` : `${user.email} заблоковано, його сеанси завершено.`,
  );

  return (
    <div className="stack">
      <h1>Користувачі</h1>
      {message && <p className={message.ok ? "success" : "error"}>{message.text}</p>}
      <table>
        <thead>
          <tr>
            <th>Користувач</th>
            {ROLES.map((role) => <th key={role}>{ROLE_LABELS[role]}</th>)}
            <th>Стан</th><th>Зареєстровано</th>
          </tr>
        </thead>
        <tbody>
          {users.map((user) => (
            <tr key={user.id} className={user.blocked ? "blocked" : ""}>
              <td>
                <strong>{user.name || "—"}</strong>
                <div className="muted">{user.email}</div>
              </td>
              {ROLES.map((role) => (
                <td key={role}>
                  <input type="checkbox" checked={user.roles.includes(role)}
                    disabled={user.id === me?._id && role === "admin"}
                    aria-label={`${ROLE_LABELS[role]} – ${user.email}`}
                    onChange={() => toggleRole(user, role)} />
                </td>
              ))}
              <td>
                {user.id === me?._id ? <span className="muted">це ви</span> : (
                  <button type="button" className={user.blocked ? "secondary" : "danger"}
                    onClick={() => toggleBlocked(user)}>
                    {user.blocked ? "Розблокувати" : "Заблокувати"}
                  </button>
                )}
              </td>
              <td className="muted">{formatDate(user.createdAt)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

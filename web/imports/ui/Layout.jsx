import { Meteor } from "meteor/meteor";
import { Navigate, NavLink, Outlet, useNavigate } from "react-router-dom";
import { ROLE_LABELS } from "/imports/api/roles";
import { hasRole, useCurrentUser } from "./hooks";

// Шапка з меню за ролями та вміст сторінки.
export function Layout() {
  const { user, roles } = useCurrentUser();
  const navigate = useNavigate();
  const logout = () => Meteor.logout(() => navigate("/login"));

  return (
    <div className="page">
      <header className="header">
        <NavLink to="/" className="brand">🎭 Квитки</NavLink>
        {user && (
          <nav className="nav">
            <NavLink to="/" end>Афіша</NavLink>
            {hasRole(roles, "buyer") && <NavLink to="/orders">Мої замовлення</NavLink>}
            {hasRole(roles, "organizer", "admin") && <NavLink to="/organizer">Організатор</NavLink>}
            {hasRole(roles, "inspector", "admin") && <NavLink to="/inspector">Контроль входу</NavLink>}
            {hasRole(roles, "admin") && <NavLink to="/admin">Адміністрування</NavLink>}
          </nav>
        )}
        {user && (
          <div className="who">
            <span>{user.profile?.name || user.emails?.[0]?.address}</span>
            <span className="muted">{roles.map((role) => ROLE_LABELS[role]).join(", ")}</span>
            <button type="button" className="link" onClick={logout}>Вийти</button>
          </div>
        )}
      </header>
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}

// Сторінка лише для користувачів із однією з ролей; без входу – на сторінку входу.
export function RequireRole({ roles: allowed = [], children }) {
  const { user, roles, loading } = useCurrentUser();
  if (loading) return <p className="muted">Завантаження…</p>;
  if (!user) return <Navigate to="/login" replace />;
  if (allowed.length && !hasRole(roles, ...allowed)) {
    return <p className="error">Недостатньо прав для цієї сторінки.</p>;
  }
  return children;
}

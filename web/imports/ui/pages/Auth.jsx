import { Meteor } from "meteor/meteor";
import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { messageOf, useCurrentUser } from "../hooks";

function loginWithPassword(email, password) {
  return new Promise((resolve, reject) =>
    Meteor.loginWithPassword({ email }, password, (error) => (error ? reject(error) : resolve())),
  );
}

export function LoginPage() {
  const { user } = useCurrentUser();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState(null);
  if (user) return <Navigate to="/" replace />;

  const submit = async (event) => {
    event.preventDefault();
    setError(null);
    try {
      await loginWithPassword(form.email.trim(), form.password);
      navigate("/");
    } catch (failure) {
      setError(failure.error === 403 ? "Невірна пошта або пароль." : messageOf(failure));
    }
  };

  return (
    <form className="card narrow" onSubmit={submit}>
      <h1>Вхід</h1>
      <label>Пошта<input type="email" required value={form.email}
        onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>
      <label>Пароль<input type="password" required value={form.password}
        onChange={(e) => setForm({ ...form, password: e.target.value })} /></label>
      {error && <p className="error">{error}</p>}
      <button type="submit">Увійти</button>
      <p className="muted">Немає облікового запису? <Link to="/register">Зареєструватися</Link></p>
    </form>
  );
}

export function RegisterPage() {
  const { user } = useCurrentUser();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [error, setError] = useState(null);
  if (user) return <Navigate to="/" replace />;

  const submit = async (event) => {
    event.preventDefault();
    setError(null);
    try {
      await Meteor.callAsync("auth.register", { ...form, email: form.email.trim() });
      await loginWithPassword(form.email.trim(), form.password);
      navigate("/");
    } catch (failure) {
      setError(messageOf(failure));
    }
  };

  return (
    <form className="card narrow" onSubmit={submit}>
      <h1>Реєстрація покупця</h1>
      <label>Ім'я<input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
      <label>Пошта<input type="email" required value={form.email}
        onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>
      <label>Пароль (щонайменше 8 символів)<input type="password" required minLength={8} value={form.password}
        onChange={(e) => setForm({ ...form, password: e.target.value })} /></label>
      {error && <p className="error">{error}</p>}
      <button type="submit">Зареєструватися</button>
      <p className="muted">Уже є обліковий запис? <Link to="/login">Увійти</Link></p>
    </form>
  );
}

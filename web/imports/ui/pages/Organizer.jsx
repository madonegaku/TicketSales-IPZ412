import { Meteor } from "meteor/meteor";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { formatDate, formatMoney } from "../format";
import { hasRole, messageOf, useCurrentUser, useMethod } from "../hooks";

// Статистика продажу: організатор бачить свої заходи, адміністратор – усі (GET /api/v1/organizer/events).
export function OrganizerPage() {
  const { roles } = useCurrentUser();
  const { data: events, error, loading } = useMethod("organizer.events");
  if (loading) return <p className="muted">Завантаження статистики…</p>;
  if (error) return <p className="error">{error}</p>;

  return (
    <div className="stack">
      <div className="row between">
        <h1>{hasRole(roles, "admin") ? "Усі заходи" : "Мої заходи"}</h1>
        <Link to="/organizer/new"><button type="button">+ Створити захід</button></Link>
      </div>
      {!events.length ? (
        <p className="muted">Заходів ще немає – створіть перший.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Захід</th><th>Початок</th><th>Продано</th><th>Зарезервовано</th><th>Вільно</th>
              <th>Оплачених замовлень</th><th>Виручка</th>
            </tr>
          </thead>
          <tbody>
            {events.map((event) => (
              <tr key={event.event_id}>
                <td><Link to={`/events/${event.event_id}`}>{event.title}</Link></td>
                <td>{formatDate(event.starts_at)}</td>
                <td>{event.seats_sold} з {event.seats_total}</td>
                <td>{event.seats_reserved}</td>
                <td>{event.seats_available}</td>
                <td>{event.paid_orders}</td>
                <td><strong>{formatMoney(event.revenue, event.currency)}</strong></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

const EMPTY_FORM = {
  title: "",
  sales_start: "",
  starts_at: "",
  categories: [{ name: "Партер", price: "500" }],
  sectors: [{ name: "Партер", rows: 5, seats_per_row: 10, category: "Партер" }],
};

// Форма створення заходу: назва, дати, цінові категорії й сектори залу (POST /api/v1/events).
export function NewEventPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const update = (list, index, field, value) =>
    setForm({ ...form, [list]: form[list].map((item, i) => (i === index ? { ...item, [field]: value } : item)) });
  const remove = (list, index) => setForm({ ...form, [list]: form[list].filter((_, i) => i !== index) });
  const seats = form.sectors.reduce((sum, s) => sum + Number(s.rows || 0) * Number(s.seats_per_row || 0), 0);

  const submit = async (event) => {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await Meteor.callAsync("organizer.createEvent", {
        title: form.title,
        // datetime-local – місцевий час браузера; toISOString() передає його з поясом (UTC)
        sales_start: new Date(form.sales_start).toISOString(),
        starts_at: new Date(form.starts_at).toISOString(),
        categories: form.categories.map(({ name, price }) => ({ name, price: String(price) })),
        sectors: form.sectors.map((s) => ({ ...s, rows: Number(s.rows), seats_per_row: Number(s.seats_per_row) })),
      });
      navigate("/organizer");
    } catch (problem) {
      setError(messageOf(problem));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="stack" onSubmit={submit}>
      <p><Link to="/organizer">← Мої заходи</Link></p>
      <h1>Новий захід</h1>
      <div className="card stack">
        <label>Назва<input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></label>
        <div className="row">
          <label>Старт продажу<input type="datetime-local" required value={form.sales_start}
            onChange={(e) => setForm({ ...form, sales_start: e.target.value })} /></label>
          <label>Початок заходу<input type="datetime-local" required value={form.starts_at}
            onChange={(e) => setForm({ ...form, starts_at: e.target.value })} /></label>
        </div>
      </div>

      <div className="card stack">
        <h2>Цінові категорії</h2>
        {form.categories.map((category, index) => (
          <div key={index} className="row">
            <label>Назва<input required value={category.name}
              onChange={(e) => update("categories", index, "name", e.target.value)} /></label>
            <label>Ціна, грн<input required inputMode="decimal" pattern="[0-9]+(\.[0-9]{1,2})?" value={category.price}
              onChange={(e) => update("categories", index, "price", e.target.value)} /></label>
            {form.categories.length > 1 && (
              <button type="button" className="secondary" onClick={() => remove("categories", index)}>Видалити</button>
            )}
          </div>
        ))}
        <button type="button" className="secondary"
          onClick={() => setForm({ ...form, categories: [...form.categories, { name: "", price: "" }] })}>
          + Категорія
        </button>
      </div>

      <div className="card stack">
        <h2>Сектори залу</h2>
        {form.sectors.map((sector, index) => (
          <div key={index} className="row">
            <label>Сектор<input required value={sector.name}
              onChange={(e) => update("sectors", index, "name", e.target.value)} /></label>
            <label>Рядів<input type="number" min="1" max="50" required value={sector.rows}
              onChange={(e) => update("sectors", index, "rows", e.target.value)} /></label>
            <label>Місць у ряду<input type="number" min="1" max="60" required value={sector.seats_per_row}
              onChange={(e) => update("sectors", index, "seats_per_row", e.target.value)} /></label>
            <label>Категорія
              <select value={sector.category} onChange={(e) => update("sectors", index, "category", e.target.value)}>
                {form.categories.map((category) => <option key={category.name}>{category.name}</option>)}
              </select>
            </label>
            {form.sectors.length > 1 && (
              <button type="button" className="secondary" onClick={() => remove("sectors", index)}>Видалити</button>
            )}
          </div>
        ))}
        <button type="button" className="secondary" onClick={() => setForm({
          ...form,
          sectors: [...form.sectors, { name: "", rows: 1, seats_per_row: 10, category: form.categories[0]?.name ?? "" }],
        })}>
          + Сектор
        </button>
        <p className="muted">Разом місць: {seats}</p>
      </div>

      {error && <p className="error">{error}</p>}
      <div><button type="submit" disabled={busy}>{busy ? "Створюємо…" : "Створити захід"}</button></div>
    </form>
  );
}

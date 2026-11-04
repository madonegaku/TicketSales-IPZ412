import { Link } from "react-router-dom";
import { formatDate, formatMoney } from "../format";
import { useMethod } from "../hooks";

// Афіша: заходи з кількістю вільних місць і ціною «від» (GET /api/v1/events у sales).
export function EventsPage() {
  const { data: events, error, loading } = useMethod("events.list");
  if (loading) return <p className="muted">Завантаження афіші…</p>;
  if (error) return <p className="error">{error}</p>;
  if (!events.length) return <p className="muted">Заходів поки немає.</p>;

  return (
    <>
      <h1>Афіша</h1>
      <div className="grid">
        {events.map((event) => (
          <Link key={event.event_id} to={`/events/${event.event_id}`} className="card event">
            <h2>{event.title}</h2>
            <p>{formatDate(event.starts_at)}</p>
            <p className="muted">Продаж з {formatDate(event.sales_start)}</p>
            <p>
              Вільно {event.seats_available} з {event.seats_total} · від {formatMoney(event.price_from, event.currency)}
            </p>
          </Link>
        ))}
      </div>
    </>
  );
}

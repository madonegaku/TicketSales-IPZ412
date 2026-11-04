import { Meteor } from "meteor/meteor";
import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { formatMoney } from "../format";
import { hasRole, messageOf, useCurrentUser, useMethod } from "../hooks";

const MAX_SEATS = 6; // С-06: не більше 6 місць на покупця (остаточно перевіряє домен sales)

const keyOf = (seat) => `${seat.sector}|${seat.row}|${seat.number}`;

// Схема залу: місця за секторами й рядами; покупець обирає до 6 вільних місць і резервує їх.
export function HallPage() {
  const { eventId } = useParams();
  const navigate = useNavigate();
  const { roles } = useCurrentUser();
  const { data: hall, error, loading, reload } = useMethod("events.hall", eventId);
  const [selected, setSelected] = useState([]);
  const [failure, setFailure] = useState(null);
  const [busy, setBusy] = useState(false);
  const isBuyer = hasRole(roles, "buyer");

  const sectors = useMemo(() => {
    const grouped = new Map();
    for (const seat of hall?.seats ?? []) {
      if (!grouped.has(seat.sector)) grouped.set(seat.sector, new Map());
      const rows = grouped.get(seat.sector);
      if (!rows.has(seat.row)) rows.set(seat.row, []);
      rows.get(seat.row).push(seat);
    }
    return [...grouped];
  }, [hall]);

  if (loading) return <p className="muted">Завантаження схеми залу…</p>;
  if (error) return <p className="error">{error}</p>;

  const toggle = (seat) => {
    setFailure(null);
    const key = keyOf(seat);
    setSelected((current) => current.some((s) => keyOf(s) === key)
      ? current.filter((s) => keyOf(s) !== key)
      : current.length < MAX_SEATS ? [...current, seat] : current);
  };
  const total = selected.reduce((sum, seat) => sum + Number(seat.price), 0);

  const reserve = async () => {
    setBusy(true);
    setFailure(null);
    try {
      const seats = selected.map(({ sector, row, number }) => ({ sector, row, number }));
      await Meteor.callAsync("orders.reserve", eventId, seats);
      navigate("/orders");
    } catch (problem) {
      setFailure(messageOf(problem));
      setSelected([]);
      reload(); // місця могли зайняти інші покупці – показати актуальний стан
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack">
      <p><Link to="/">← Афіша</Link></p>
      <h1>{hall.title}</h1>
      <div className="legend">
        <span className="seat free" /> вільне <span className="seat taken" /> зайняте
        {isBuyer && <><span className="seat chosen" /> обране</>}
      </div>
      {sectors.map(([sector, rows]) => (
        <section key={sector} className="card">
          <h2>{sector}</h2>
          {[...rows].map(([row, seats]) => (
            <div key={row} className="seat-row">
              <span className="row-label">Ряд {row}</span>
              {seats.map((seat) => {
                const chosen = selected.some((s) => keyOf(s) === keyOf(seat));
                return (
                  <button
                    key={keyOf(seat)}
                    type="button"
                    className={`seat ${!seat.is_available ? "taken" : chosen ? "chosen" : "free"}`}
                    disabled={!seat.is_available || !isBuyer}
                    title={`${seat.sector}, ряд ${seat.row}, місце ${seat.number} – ${formatMoney(seat.price, seat.currency)}`}
                    onClick={() => toggle(seat)}
                  >
                    {seat.number}
                  </button>
                );
              })}
            </div>
          ))}
        </section>
      ))}
      {isBuyer ? (
        <div className="card row">
          <span>
            Обрано {selected.length} з {MAX_SEATS} · {formatMoney(total)}
          </span>
          <button type="button" disabled={!selected.length || busy} onClick={reserve}>
            {busy ? "Резервуємо…" : "Зарезервувати на 15 хвилин"}
          </button>
          {failure && <span className="error">{failure}</span>}
        </div>
      ) : (
        <p className="muted">Резервувати місця може лише покупець.</p>
      )}
    </div>
  );
}

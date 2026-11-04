import { Meteor } from "meteor/meteor";
import QRCode from "qrcode";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { formatDate, formatMoney, ORDER_STATUS, TICKET_STATUS } from "../format";
import { messageOf, useMethod } from "../hooks";

// «Мої замовлення»: оплата й квитки з QR-кодами (квитки видає tickets після події OrderPaid).
export function OrdersPage() {
  const { data: orders, error, loading, reload } = useMethod("orders.mine");
  if (loading) return <p className="muted">Завантаження замовлень…</p>;
  if (error) return <p className="error">{error}</p>;
  if (!orders.length) return <p className="muted">Замовлень ще немає. Оберіть місця в <Link to="/">афіші</Link>.</p>;

  return (
    <div className="stack">
      <h1>Мої замовлення</h1>
      {orders.map((order) => <OrderCard key={order.order_id} order={order} onChange={reload} />)}
    </div>
  );
}

function OrderCard({ order, onChange }) {
  const [message, setMessage] = useState(null);
  const [busy, setBusy] = useState(false);
  const expired = order.status === "AWAITING_PAYMENT" && new Date(order.payment_deadline) <= new Date();

  const pay = async () => {
    setBusy(true);
    setMessage(null);
    try {
      await Meteor.callAsync("orders.pay", order.order_id);
      onChange();
    } catch (problem) {
      // payment_unavailable: оплата в обробці, повтор безпечний (ідемпотентність за order_id, ЛР 3)
      setMessage({ error: problem.error === "payment_unavailable", text: messageOf(problem) });
      onChange();
    } finally {
      setBusy(false);
    }
  };

  return (
    <article className="card stack">
      <div className="row between">
        <div>
          <h2>{order.event_title}</h2>
          <p className="muted">
            {order.seats.map((s) => `${s.sector}, ряд ${s.row}, № ${s.number}`).join(" · ")}
          </p>
        </div>
        <div className="right">
          <strong>{formatMoney(order.total_amount, order.currency)}</strong>
          <p className={`badge ${order.status}`}>{ORDER_STATUS[order.status]}</p>
        </div>
      </div>
      {order.status !== "PAID" && (
        <div className="row">
          {expired ? (
            <span className="muted">Строк резервування минув – оберіть місця знову.</span>
          ) : (
            <>
              <button type="button" disabled={busy} onClick={pay}>
                {busy ? "Оплачуємо…" : order.status === "PAYMENT_PENDING" ? "Спробувати ще раз" : "Оплатити"}
              </button>
              {order.status === "AWAITING_PAYMENT" && (
                <span className="muted">Оплатити до {formatDate(order.payment_deadline)}</span>
              )}
            </>
          )}
          {message && <span className="error">{message.text}</span>}
        </div>
      )}
      {order.status === "PAID" && <Tickets orderId={order.order_id} />}
    </article>
  );
}

// Квитки з'являються в tickets приблизно через секунду після оплати (ЛР 5) – опитуємо кілька разів.
function Tickets({ orderId }) {
  const [tickets, setTickets] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let attempts = 0;
    let timer;
    let cancelled = false;
    const load = async () => {
      try {
        const result = await Meteor.callAsync("orders.tickets", orderId);
        if (cancelled) return;
        setTickets(result.tickets);
        if (!result.tickets.length && ++attempts < 20) timer = setTimeout(load, 1500);
      } catch (problem) {
        if (!cancelled) setError(messageOf(problem));
      }
    };
    load();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [orderId]);

  if (error) return <p className="error">{error}</p>;
  if (!tickets) return <p className="muted">Завантаження квитків…</p>;
  if (!tickets.length) return <p className="muted">Квитки ще видаються…</p>;
  return (
    <div className="grid tickets">
      {tickets.map((ticket) => <TicketCard key={ticket.code} ticket={ticket} />)}
    </div>
  );
}

function TicketCard({ ticket }) {
  const [qr, setQr] = useState(null);
  useEffect(() => {
    QRCode.toDataURL(ticket.code, { width: 160, margin: 1 }).then(setQr);
  }, [ticket.code]);
  return (
    <div className="ticket">
      {qr && <img src={qr} alt={`QR-код квитка ${ticket.code}`} />}
      <div>
        <strong>{ticket.sector}, ряд {ticket.row}, № {ticket.number}</strong>
        <p className="muted code">{ticket.code}</p>
        <p className={`badge ${ticket.status}`}>{TICKET_STATUS[ticket.status]}</p>
      </div>
    </div>
  );
}

import { Meteor } from "meteor/meteor";
import { useEffect, useRef, useState } from "react";
import { messageOf, useMethod } from "../hooks";

// Контроль на вході: контролер обирає захід і вводить (або сканує сканером-клавіатурою) код квитка.
// Повторний код відхиляється (С-07) – це вирішує tickets, а не інтерфейс.
export function InspectorPage() {
  const { data: events, error, loading } = useMethod("events.list");
  const [eventId, setEventId] = useState("");
  const [code, setCode] = useState("");
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const input = useRef(null);

  useEffect(() => {
    if (events?.length && !eventId) setEventId(events[0].event_id);
  }, [events, eventId]);

  if (loading) return <p className="muted">Завантаження заходів…</p>;
  if (error) return <p className="error">{error}</p>;

  const check = async (event) => {
    event.preventDefault();
    const scanned = code.trim();
    if (!scanned) return;
    let outcome;
    try {
      const seat = await Meteor.callAsync("inspector.validate", scanned, eventId);
      outcome = { ok: true, text: `Прохід дозволено: ${seat.sector}, ряд ${seat.row}, № ${seat.number}` };
    } catch (problem) {
      outcome = { ok: false, text: `Прохід заборонено: ${messageOf(problem)}` };
    }
    setResult(outcome);
    setHistory((items) => [{ code: scanned, ...outcome, at: new Date() }, ...items].slice(0, 10));
    setCode("");
    input.current?.focus();
  };

  return (
    <div className="stack">
      <h1>Контроль входу</h1>
      <form className="card stack" onSubmit={check}>
        <label>Захід
          <select value={eventId} onChange={(e) => { setEventId(e.target.value); setResult(null); }}>
            {events.map((item) => <option key={item.event_id} value={item.event_id}>{item.title}</option>)}
          </select>
        </label>
        <label>Код квитка
          <input ref={input} autoFocus value={code} placeholder="Відскануйте QR або введіть код"
            onChange={(e) => setCode(e.target.value)} />
        </label>
        <div><button type="submit" disabled={!code.trim() || !eventId}>Перевірити</button></div>
      </form>
      {result && <div className={`verdict ${result.ok ? "ok" : "denied"}`}>{result.text}</div>}
      {history.length > 0 && (
        <table>
          <thead><tr><th>Час</th><th>Код</th><th>Результат</th></tr></thead>
          <tbody>
            {history.map((item, index) => (
              <tr key={index}>
                <td>{item.at.toLocaleTimeString("uk-UA")}</td>
                <td className="code">{item.code}</td>
                <td className={item.ok ? "success" : "error"}>{item.text}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

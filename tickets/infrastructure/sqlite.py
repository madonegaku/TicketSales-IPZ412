"""Сховище квитків у SQLite – власна база сервісу tickets.

Нею користуються два процеси одного сервісу: споживач подій (видає квитки) і веб-сторінки
(контроль на вході, «Мої квитки»). Інші сервіси до неї не звертаються.
"""

import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import UUID

from tickets.domain.exceptions import NotFoundError
from tickets.domain.repositories import TicketRepository
from tickets.domain.ticket import Ticket, TicketStatus
from tickets.domain.value_objects import SeatPosition

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    code TEXT PRIMARY KEY,
    ticket_id TEXT NOT NULL UNIQUE,
    order_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    sector TEXT NOT NULL,
    seat_row INTEGER NOT NULL,
    seat_number INTEGER NOT NULL,
    status TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS tickets_by_order ON tickets (order_id);
"""

COLUMNS = "code, ticket_id, order_id, event_id, sector, seat_row, seat_number, status"
INSERT = f"INSERT INTO tickets ({COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
UPSERT = INSERT + " ON CONFLICT(code) DO UPDATE SET status = excluded.status"


def to_row(ticket: Ticket) -> tuple:
    position = ticket.position
    return (
        ticket.code,
        str(ticket.id),
        str(ticket.order_id),
        str(ticket.event_id),
        position.sector,
        position.row,
        position.number,
        ticket.status.name,
    )


def to_ticket(row: tuple) -> Ticket:
    code, ticket_id, order_id, event_id, sector, seat_row, seat_number, status = row
    position = SeatPosition(sector, seat_row, seat_number)
    return Ticket(UUID(ticket_id), UUID(order_id), UUID(event_id), position, code, TicketStatus[status])


class SqliteTicketRepository(TicketRepository):
    """Квитки в таблиці tickets; квитки одного замовлення додаються в одній транзакції."""

    def __init__(self, path: str | Path) -> None:
        self._path = str(path)
        with closing(sqlite3.connect(self._path)) as connection, connection:
            connection.executescript(SCHEMA)

    def _select(self, sql: str, params: tuple) -> list[tuple]:
        with closing(sqlite3.connect(self._path)) as connection:
            return connection.execute(sql, params).fetchall()

    def get_by_code(self, code: str) -> Ticket:
        rows = self._select(f"SELECT {COLUMNS} FROM tickets WHERE code = ?", (code,))
        if not rows:
            raise NotFoundError("Квиток не знайдено.")
        return to_ticket(rows[0])

    def save(self, ticket: Ticket) -> None:
        with closing(sqlite3.connect(self._path)) as connection, connection:
            connection.execute(UPSERT, to_row(ticket))

    def add_all(self, tickets: list[Ticket]) -> None:
        with closing(sqlite3.connect(self._path)) as connection, connection:
            connection.executemany(INSERT, [to_row(ticket) for ticket in tickets])

    def exists_for_order(self, order_id: UUID) -> bool:
        return bool(self._select("SELECT 1 FROM tickets WHERE order_id = ? LIMIT 1", (str(order_id),)))

    def list_by_order(self, order_id: UUID) -> list[Ticket]:
        sql = f"SELECT {COLUMNS} FROM tickets WHERE order_id = ? ORDER BY rowid"
        return [to_ticket(row) for row in self._select(sql, (str(order_id),))]
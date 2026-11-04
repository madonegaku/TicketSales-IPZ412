"""Вихідна черга подій у PostgreSQL (transactional outbox) – реалізація доменного Outbox.

add() викликається всередині одиниці роботи PayOrder і пише в те саме з'єднання й ту саму
транзакцію, що й статус замовлення. pending() і mark_published() викликає «поштар»
(OutboxRelay) окремими короткими транзакціями. У таблиці – доменні поля події; формат
повідомлення за контрактом формує публікатор (redis_publisher.to_message).
"""

from datetime import datetime
from uuid import UUID

from psycopg.types.json import Jsonb

from sales.domain.order_paid import OrderPaid
from sales.domain.outbox import Outbox
from sales.domain.value_objects import SeatPosition
from sales.infrastructure.postgres.database import Database

PENDING_BATCH = 100


def to_payload(event: OrderPaid) -> dict:
    return {
        "occurred_at": event.occurred_at.isoformat(),
        "order_id": str(event.order_id),
        "event_id": str(event.event_id),
        "event_title": event.event_title,
        "event_starts_at": event.event_starts_at.isoformat(),
        "seats": [[seat.sector, seat.row, seat.number] for seat in event.seats],
    }


def from_payload(message_id: UUID, payload: dict) -> OrderPaid:
    return OrderPaid(
        message_id,
        datetime.fromisoformat(payload["occurred_at"]),
        UUID(payload["order_id"]),
        UUID(payload["event_id"]),
        payload["event_title"],
        datetime.fromisoformat(payload["event_starts_at"]),
        tuple(SeatPosition(sector, row, number) for sector, row, number in payload["seats"]),
    )


class PostgresOutbox(Outbox):
    """Таблиця outbox: подія лишається неопублікованою, доки брокер не прийме її."""

    def __init__(self, database: Database) -> None:
        self._db = database

    def add(self, event: OrderPaid) -> None:
        with self._db.connection() as connection:
            connection.execute(
                "INSERT INTO outbox (message_id, message_type, payload) VALUES (%s, %s, %s)",
                (event.message_id, "OrderPaid", Jsonb(to_payload(event))),
            )

    def pending(self) -> list[OrderPaid]:
        with self._db.connection() as connection:
            rows = connection.execute(
                "SELECT message_id, payload FROM outbox WHERE published_at IS NULL ORDER BY position LIMIT %s",
                (PENDING_BATCH,),
            ).fetchall()
        return [from_payload(message_id, payload) for message_id, payload in rows]

    def mark_published(self, message_id: UUID) -> None:
        with self._db.connection() as connection:
            connection.execute(
                "UPDATE outbox SET published_at = now() WHERE message_id = %s AND published_at IS NULL",
                (message_id,),
            )

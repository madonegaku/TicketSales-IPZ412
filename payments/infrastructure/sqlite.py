"""Сховище платежів у SQLite – власна база сервісу payments; інші сервіси до неї не звертаються."""

import sqlite3
from contextlib import closing
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from payments.domain.payment import Payment, PaymentStatus
from payments.domain.repositories import PaymentRepository
from payments.domain.value_objects import Money
from payments.infrastructure.migrate import migrate

SELECT_BY_ORDER = """
SELECT payment_id, order_id, amount, currency, status, decline_reason, created_at
FROM payments WHERE order_id = ?
"""

UPSERT = """
INSERT INTO payments (order_id, payment_id, amount, currency, status, decline_reason, created_at)
VALUES (?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(order_id) DO UPDATE SET
    payment_id = excluded.payment_id,
    amount = excluded.amount,
    currency = excluded.currency,
    status = excluded.status,
    decline_reason = excluded.decline_reason,
    created_at = excluded.created_at
"""


class SqlitePaymentRepository(PaymentRepository):
    """Платежі в таблиці payments; order_id – первинний ключ, тож двох платежів на замовлення бути не може.

    Нова спроба після відмови замінює відхилений платіж (ON CONFLICT … DO UPDATE).
    """

    def __init__(self, path: str | Path) -> None:
        self._path = str(path)
        with closing(sqlite3.connect(self._path)) as connection:
            migrate(connection)

    def find_by_order(self, order_id: UUID) -> Payment | None:
        with closing(sqlite3.connect(self._path)) as connection:
            row = connection.execute(SELECT_BY_ORDER, (str(order_id),)).fetchone()
        if row is None:
            return None
        payment_id, order, amount, currency, status, decline_reason, created_at = row
        return Payment(
            UUID(payment_id),
            UUID(order),
            Money(Decimal(amount), currency),
            PaymentStatus(status),
            datetime.fromisoformat(created_at),
            decline_reason,
        )

    def save(self, payment: Payment) -> None:
        values = (
            str(payment.order_id),
            str(payment.id),
            str(payment.amount.amount),
            payment.amount.currency,
            payment.status.value,
            payment.decline_reason,
            payment.created_at.isoformat(),
        )
        with closing(sqlite3.connect(self._path)) as connection, connection:
            connection.execute(UPSERT, values)
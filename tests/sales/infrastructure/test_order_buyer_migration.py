"""Міграції 0003–0004 sales за шаблоном «розширення – скорочення»: покупець замовлення.

Попередня версія коду (ЛР 5) пише замовлення без buyer_id. Її запит «заморожено» тут, як у
тестах сумісності payments: після 0003 вона має працювати, а її замовлення – отримати покупця.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

psycopg = pytest.importorskip("psycopg")

from sales.infrastructure.postgres.migrate import migrate  # noqa: E402

NOW = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)
LAB5_INSERT_ORDER = (
    "INSERT INTO orders (id, reservation_id, event_id, payment_deadline, status) VALUES (%s, %s, %s, %s, %s)"
)


@pytest.fixture
def db(pg_conninfo):
    with psycopg.connect(pg_conninfo, autocommit=True) as connection:
        yield connection


def lab5_order(db, buyer):
    """Захід, резервування покупця й замовлення так, як їх пише код ЛР 5 (без buyer_id)."""
    event_id, reservation_id, order_id = uuid4(), uuid4(), uuid4()
    db.execute("INSERT INTO events VALUES (%s, 'Концерт', %s, %s)", (event_id, NOW, NOW + timedelta(days=30)))
    db.execute("INSERT INTO reservations VALUES (%s, %s, %s, %s)", (reservation_id, event_id, buyer, NOW))
    db.execute(LAB5_INSERT_ORDER, (order_id, reservation_id, event_id, NOW + timedelta(minutes=15),
                                   "AWAITING_PAYMENT"))
    return order_id


def buyer_of(db, order_id):
    return db.execute("SELECT buyer_id FROM orders WHERE id = %s", (order_id,)).fetchone()[0]


def test_0003_fills_buyer_of_existing_orders_and_keeps_lab5_code_working(db):
    migrate(db, target=2)
    buyer = uuid4()
    before = lab5_order(db, buyer)

    migrate(db, target=3)
    after = lab5_order(db, buyer)

    assert buyer_of(db, before) == buyer
    assert buyer_of(db, after) is None, "ЛР 5 після 0003 працює, buyer_id ще не обов'язковий"


def test_0004_fills_orders_written_after_0003_and_makes_buyer_required(db):
    migrate(db, target=3)
    buyer = uuid4()
    written_by_lab5 = lab5_order(db, buyer)

    migrate(db, target=4)

    assert buyer_of(db, written_by_lab5) == buyer
    with pytest.raises(psycopg.errors.NotNullViolation):
        lab5_order(db, buyer)

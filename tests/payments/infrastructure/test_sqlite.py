"""Тести сховища платежів у SQLite: відповідність контракту інтерфейсу й збереження після перезапуску."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from payments.domain.payment import Payment, PaymentStatus
from payments.domain.value_objects import Money
from payments.infrastructure.sqlite import SqlitePaymentRepository

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)
AMOUNT = Money(Decimal("1200.00"))


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "payments.sqlite3"


def test_saved_payment_is_found_by_order(db_path):
    repository = SqlitePaymentRepository(db_path)
    payment = Payment.declined(uuid4(), AMOUNT, "Недостатньо коштів", NOW)

    repository.save(payment)
    found = repository.find_by_order(payment.order_id)

    assert (found.id, found.amount, found.status) == (payment.id, AMOUNT, PaymentStatus.DECLINED)
    assert (found.decline_reason, found.created_at) == ("Недостатньо коштів", NOW)


def test_missing_payment_is_none(db_path):
    assert SqlitePaymentRepository(db_path).find_by_order(uuid4()) is None


def test_new_attempt_after_decline_replaces_payment(db_path):
    repository = SqlitePaymentRepository(db_path)
    order_id = uuid4()
    repository.save(Payment.declined(order_id, AMOUNT, "Недостатньо коштів", NOW))

    repository.save(Payment.succeeded(order_id, AMOUNT, NOW))

    assert repository.find_by_order(order_id).status is PaymentStatus.SUCCEEDED


def test_payment_survives_service_restart(db_path):
    payment = Payment.succeeded(uuid4(), AMOUNT, NOW)
    SqlitePaymentRepository(db_path).save(payment)

    after_restart = SqlitePaymentRepository(db_path)

    assert after_restart.find_by_order(payment.order_id).id == payment.id
"""Тести агрегату Payment: інваріанти та правило ідемпотентності (С-04, С-05)."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from payments.domain.exceptions import IdempotencyConflictError, InvalidPaymentError
from payments.domain.payment import Payment, PaymentStatus
from payments.domain.value_objects import Money

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)
AMOUNT = Money(Decimal("1200"))


def test_succeeded_payment_has_no_decline_reason():
    payment = Payment.succeeded(uuid4(), AMOUNT, NOW)

    assert payment.status is PaymentStatus.SUCCEEDED
    assert payment.decline_reason is None


def test_declined_payment_keeps_reason():
    payment = Payment.declined(uuid4(), AMOUNT, "Недостатньо коштів", NOW)

    assert payment.status is PaymentStatus.DECLINED
    assert payment.decline_reason == "Недостатньо коштів"


def test_declined_payment_without_reason_is_rejected():
    with pytest.raises(InvalidPaymentError):
        Payment(uuid4(), uuid4(), AMOUNT, PaymentStatus.DECLINED, NOW)


def test_zero_amount_payment_is_rejected():
    with pytest.raises(InvalidPaymentError):
        Payment.succeeded(uuid4(), Money(Decimal("0")), NOW)


@pytest.mark.parametrize("amount", [Money(Decimal("1200")), Money(Decimal("1200.00"))])
def test_repeated_request_with_same_amount_is_accepted(amount):
    payment = Payment.succeeded(uuid4(), AMOUNT, NOW)

    payment.ensure_same_request(amount)


@pytest.mark.parametrize("amount", [Money(Decimal("1500")), Money(Decimal("1200"), "USD")])
def test_repeated_request_with_other_amount_or_currency_is_conflict(amount):
    payment = Payment.succeeded(uuid4(), AMOUNT, NOW)

    with pytest.raises(IdempotencyConflictError):
        payment.ensure_same_request(amount)


def test_only_succeeded_payment_is_final():
    assert Payment.succeeded(uuid4(), AMOUNT, NOW).is_final
    assert not Payment.declined(uuid4(), AMOUNT, "Недостатньо коштів", NOW).is_final
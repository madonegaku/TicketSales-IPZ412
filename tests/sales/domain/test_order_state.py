"""Тести станів замовлення (патерн State, ЛР 4): кожен стан перевіряється окремо, без Order."""

from datetime import datetime, timedelta, timezone

import pytest

from sales.domain.exceptions import InvalidOrderError, OrderAlreadyPaidError, ReservationExpiredError
from sales.domain.order_state import STATES, AwaitingPayment, OrderStatus, Paid, PaymentPending, state_of

DEADLINE = datetime(2026, 11, 5, 12, 15, tzinfo=timezone.utc)
BEFORE, AT = DEADLINE - timedelta(seconds=1), DEADLINE


def test_every_status_has_a_state():
    assert set(STATES) == set(OrderStatus)
    assert isinstance(state_of(OrderStatus.AWAITING_PAYMENT), AwaitingPayment)
    assert isinstance(state_of(OrderStatus.PAYMENT_PENDING), PaymentPending)
    assert isinstance(state_of(OrderStatus.PAID), Paid)


def test_awaiting_payment_starts_only_before_deadline():
    assert AwaitingPayment().start_payment(DEADLINE, BEFORE) is OrderStatus.PAYMENT_PENDING
    with pytest.raises(ReservationExpiredError):
        AwaitingPayment().start_payment(DEADLINE, AT)


def test_payment_pending_transitions():
    state = PaymentPending()

    assert state.resume_payment(DEADLINE, AT) is OrderStatus.PAYMENT_PENDING
    assert state.cancel_payment() is OrderStatus.AWAITING_PAYMENT
    assert state.confirm_payment() is OrderStatus.PAID
    with pytest.raises(InvalidOrderError):
        state.start_payment(DEADLINE, BEFORE)


def test_paid_rejects_payment_operations():
    state = Paid()

    for operation in (lambda: state.start_payment(DEADLINE, BEFORE), lambda: state.resume_payment(DEADLINE, BEFORE),
                      state.confirm_payment):
        with pytest.raises(OrderAlreadyPaidError):
            operation()
    with pytest.raises(InvalidOrderError):
        state.cancel_payment()

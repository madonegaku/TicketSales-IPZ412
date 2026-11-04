"""Характеризаційні тести ЛР 4: повна таблиця «стан замовлення × операція» до рефакторингу Order.

Фіксують поточну поведінку: для кожної пари – новий стан або точний тип і текст винятку.
Після заміни умов на патерн State ці тести мають проходити без жодних змін.
"""

import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from sales.domain.event import Event, PriceCategory, Seat
from sales.domain.exceptions import InvalidOrderError, OrderAlreadyPaidError, ReservationExpiredError
from sales.domain.order import Order, OrderStatus
from sales.domain.reservation import Reservation
from sales.domain.value_objects import Money, SeatPosition

NOW = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)
A1 = SeatPosition("Партер", 1, 1)

ALREADY_STARTED = "Оплата цього замовлення вже розпочата."
ALREADY_PAID = "Замовлення вже оплачене."
EXPIRED = "Строк резервування минув – оберіть місця знову."
NOT_STARTED_CONFIRM = "Не можна підтвердити оплату, яку не розпочато."
NOT_STARTED_CANCEL = "Скасувати можна лише розпочату й незавершену оплату."


def order_in(status: OrderStatus) -> Order:
    categories = {"Партер": PriceCategory("Партер", Money(Decimal("600")))}
    event = Event(uuid4(), "Концерт", NOW - timedelta(days=1), categories, {A1: Seat(A1, "Партер")},
                  NOW + timedelta(days=30))
    order = Order.for_reservation(Reservation.create(event.id, uuid4(), [A1], NOW, 0), event)
    if status is not OrderStatus.AWAITING_PAYMENT:
        order.start_payment(NOW)
    if status is OrderStatus.PAID:
        order.confirm_payment()
    return order


IN_TIME = NOW + timedelta(minutes=5)
TOO_LATE = NOW + timedelta(minutes=15)

OPERATIONS = {
    "start_payment": lambda order: order.start_payment(IN_TIME),
    "start_payment_too_late": lambda order: order.start_payment(TOO_LATE),
    "start_or_resume_payment": lambda order: order.start_or_resume_payment(IN_TIME),
    "start_or_resume_payment_too_late": lambda order: order.start_or_resume_payment(TOO_LATE),
    "cancel_payment": lambda order: order.cancel_payment(),
    "confirm_payment": lambda order: order.confirm_payment(),
}

AWAITING, PENDING, PAID = OrderStatus.AWAITING_PAYMENT, OrderStatus.PAYMENT_PENDING, OrderStatus.PAID

# (стан, операція) → новий стан або (виняток, повідомлення)
EXPECTED = {
    (AWAITING, "start_payment"): PENDING,
    (AWAITING, "start_payment_too_late"): (ReservationExpiredError, EXPIRED),
    (AWAITING, "start_or_resume_payment"): PENDING,
    (AWAITING, "start_or_resume_payment_too_late"): (ReservationExpiredError, EXPIRED),
    (AWAITING, "cancel_payment"): (InvalidOrderError, NOT_STARTED_CANCEL),
    (AWAITING, "confirm_payment"): (InvalidOrderError, NOT_STARTED_CONFIRM),
    (PENDING, "start_payment"): (InvalidOrderError, ALREADY_STARTED),
    (PENDING, "start_payment_too_late"): (InvalidOrderError, ALREADY_STARTED),
    (PENDING, "start_or_resume_payment"): PENDING,
    (PENDING, "start_or_resume_payment_too_late"): PENDING,
    (PENDING, "cancel_payment"): AWAITING,
    (PENDING, "confirm_payment"): PAID,
    (PAID, "start_payment"): (OrderAlreadyPaidError, ALREADY_PAID),
    (PAID, "start_payment_too_late"): (OrderAlreadyPaidError, ALREADY_PAID),
    (PAID, "start_or_resume_payment"): (OrderAlreadyPaidError, ALREADY_PAID),
    (PAID, "start_or_resume_payment_too_late"): (OrderAlreadyPaidError, ALREADY_PAID),
    (PAID, "cancel_payment"): (InvalidOrderError, NOT_STARTED_CANCEL),
    (PAID, "confirm_payment"): (OrderAlreadyPaidError, ALREADY_PAID),
}


@pytest.mark.parametrize(("status", "operation"), list(EXPECTED), ids=lambda v: getattr(v, "name", v))
def test_order_transition_table(status, operation):
    order = order_in(status)
    expected = EXPECTED[(status, operation)]

    if isinstance(expected, OrderStatus):
        OPERATIONS[operation](order)
        assert order.status is expected
    else:
        error, message = expected
        with pytest.raises(error, match=f"^{re.escape(message)}$"):
            OPERATIONS[operation](order)
        assert order.status is status, "відхилена операція не змінює стан"


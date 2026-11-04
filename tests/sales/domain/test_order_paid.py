"""Тести доменної події OrderPaid: створюється лише для оплаченого замовлення."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from sales.domain.event import Event, PriceCategory, Seat
from sales.domain.exceptions import InvalidOrderError
from sales.domain.order import Order
from sales.domain.order_paid import OrderPaid
from sales.domain.reservation import Reservation
from sales.domain.value_objects import Money, SeatPosition

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
STARTS_AT = NOW + timedelta(days=30)
A1 = SeatPosition("Партер", 1, 1)


def make_event_and_order():
    categories = {"Партер": PriceCategory("Партер", Money(Decimal("600")))}
    event = Event(uuid4(), "Концерт", NOW - timedelta(days=1), categories, {A1: Seat(A1, "Партер")}, STARTS_AT)
    reservation = Reservation.create(event.id, uuid4(), [A1], NOW, seats_already_held=0)
    return event, Order.for_reservation(reservation, event)


def test_order_paid_carries_order_event_and_seats():
    event, order = make_event_and_order()
    order.start_payment(NOW)
    order.confirm_payment()

    paid = OrderPaid.for_order(order, event, NOW)

    assert (paid.order_id, paid.event_id, paid.event_title) == (order.id, event.id, "Концерт")
    assert (paid.event_starts_at, paid.seats) == (STARTS_AT, (A1,))


def test_order_paid_for_unpaid_order_is_rejected():
    event, order = make_event_and_order()

    with pytest.raises(InvalidOrderError):
        OrderPaid.for_order(order, event, NOW)
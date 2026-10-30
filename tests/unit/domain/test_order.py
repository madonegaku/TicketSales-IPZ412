"""Тести агрегату Order: фіксація цін, сума, оплата (С-04, С-05)."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from ticketing.domain.event import Event, PriceCategory, Seat
from ticketing.domain.exceptions import (
    InvalidOrderError,
    OrderAlreadyPaidError,
    ReservationExpiredError,
)
from ticketing.domain.order import Order, OrderStatus
from ticketing.domain.reservation import Reservation
from ticketing.domain.value_objects import Money, SeatPosition

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
A1 = SeatPosition("Партер", 1, 1)
VIP = SeatPosition("VIP", 1, 1)


def make_event():
    categories = {
        "Партер": PriceCategory("Партер", Money(Decimal("600"))),
        "VIP": PriceCategory("VIP", Money(Decimal("1500"))),
    }
    seats = {A1: Seat(A1, "Партер"), VIP: Seat(VIP, "VIP")}
    return Event(uuid4(), "Концерт", NOW - timedelta(days=1), categories, seats)


def make_order(event=None):
    event = event or make_event()
    reservation = Reservation.create(event.id, uuid4(), [A1, VIP], NOW, seats_already_held=0)
    return Order.for_reservation(reservation, event)


def test_order_total_is_sum_of_seat_prices():
    assert make_order().total == Money(Decimal("2100"))


def test_price_change_after_reservation_does_not_change_order_total():
    event = make_event()
    order = make_order(event)

    event.categories["VIP"].price = Money(Decimal("3000"))

    assert order.total == Money(Decimal("2100"))


def test_order_for_reservation_of_another_event_is_rejected():
    reservation = Reservation.create(uuid4(), uuid4(), [A1], NOW, seats_already_held=0)

    with pytest.raises(InvalidOrderError):
        Order.for_reservation(reservation, make_event())


def test_payment_started_in_time_is_confirmed_even_after_reservation_expires():
    order = make_order()

    order.start_payment(NOW + timedelta(minutes=14, seconds=50))
    order.confirm_payment()

    assert order.status is OrderStatus.PAID


def test_payment_cannot_be_started_after_reservation_expires():
    order = make_order()

    with pytest.raises(ReservationExpiredError):
        order.start_payment(NOW + timedelta(minutes=15))


def test_order_cannot_be_paid_twice():
    order = make_order()
    order.start_payment(NOW)
    order.confirm_payment()

    with pytest.raises(OrderAlreadyPaidError):
        order.confirm_payment()


def test_payment_cannot_be_confirmed_without_being_started():
    order = make_order()

    with pytest.raises(InvalidOrderError):
        order.confirm_payment()
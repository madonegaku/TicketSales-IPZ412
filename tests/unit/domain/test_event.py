"""Тести агрегату Event: правила резервування місць (С-03)."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from ticketing.domain.event import Event, PriceCategory, Seat, SeatStatus
from ticketing.domain.exceptions import (
    InvalidSeatSelectionError,
    InvalidSeatTransitionError,
    SalesNotStartedError,
    SeatNotAvailableError,
    UnknownPriceCategoryError,
)
from ticketing.domain.value_objects import Money, SeatPosition

SALES_START = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
AFTER_START = SALES_START + timedelta(hours=1)
A1 = SeatPosition("Партер", 1, 1)
A2 = SeatPosition("Партер", 1, 2)
VIP = SeatPosition("VIP", 1, 1)


def make_event():
    categories = {
        "Партер": PriceCategory("Партер", Money(Decimal("600"))),
        "VIP": PriceCategory("VIP", Money(Decimal("1500"))),
    }
    seats = {
        A1: Seat(A1, "Партер"),
        A2: Seat(A2, "Партер"),
        VIP: Seat(VIP, "VIP"),
    }
    return Event(uuid4(), "Концерт", SALES_START, categories, seats)


def test_seats_are_reserved_after_sales_start():
    event = make_event()

    event.reserve_seats([A1, VIP], now=AFTER_START)

    assert event.seats[A1].status is SeatStatus.RESERVED
    assert event.seats[VIP].status is SeatStatus.RESERVED


def test_reservation_before_sales_start_is_rejected():
    event = make_event()

    with pytest.raises(SalesNotStartedError):
        event.reserve_seats([A1], now=SALES_START - timedelta(minutes=1))


def test_same_seat_cannot_be_reserved_twice():
    event = make_event()
    event.reserve_seats([A1], now=AFTER_START)

    with pytest.raises(SeatNotAvailableError):
        event.reserve_seats([A1], now=AFTER_START)


def test_reservation_is_all_or_nothing():
    event = make_event()
    event.reserve_seats([A2], now=AFTER_START)

    with pytest.raises(SeatNotAvailableError):
        event.reserve_seats([A1, A2], now=AFTER_START)

    assert event.seats[A1].status is SeatStatus.AVAILABLE


def test_duplicate_seat_in_selection_is_rejected():
    event = make_event()

    with pytest.raises(InvalidSeatSelectionError):
        event.reserve_seats([A1, A1], now=AFTER_START)

    assert event.seats[A1].status is SeatStatus.AVAILABLE


def test_seat_outside_hall_layout_is_rejected():
    event = make_event()

    with pytest.raises(InvalidSeatSelectionError):
        event.reserve_seats([SeatPosition("Балкон", 1, 1)], now=AFTER_START)


def test_price_of_seat_is_its_category_price():
    event = make_event()

    assert event.price_of(VIP) == Money(Decimal("1500"))
    assert event.price_of(A1) == Money(Decimal("600"))


def test_event_with_seat_in_unknown_category_cannot_be_created():
    with pytest.raises(UnknownPriceCategoryError):
        Event(uuid4(), "Концерт", SALES_START, {}, {A1: Seat(A1, "Партер")})


def test_reserved_seats_are_sold():
    event = make_event()
    event.reserve_seats([A1, VIP], now=AFTER_START)

    event.sell_seats([A1, VIP])

    assert event.seats[A1].status is SeatStatus.SOLD
    assert event.seats[VIP].status is SeatStatus.SOLD


def test_selling_is_all_or_nothing():
    event = make_event()
    event.reserve_seats([A1], now=AFTER_START)

    with pytest.raises(InvalidSeatTransitionError):
        event.sell_seats([A1, A2])

    assert event.seats[A1].status is SeatStatus.RESERVED
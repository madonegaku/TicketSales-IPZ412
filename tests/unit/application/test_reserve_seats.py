"""Тести сценарію ReserveSeats: проходження через шари без бази даних."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from ticketing.application.reserve_seats import ReserveSeats, ReserveSeatsCommand
from ticketing.domain.event import Event, PriceCategory, Seat, SeatStatus
from ticketing.domain.exceptions import ReservationLimitError, SeatNotAvailableError
from ticketing.domain.value_objects import Money, SeatPosition
from ticketing.infrastructure.in_memory import (
    InMemoryEventRepository,
    InMemoryOrderRepository,
    InMemoryReservationRepository,
)

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
EVENT_ID = uuid4()
BUYER_ID = uuid4()
SEATS = [SeatPosition("Партер", 1, number) for number in range(1, 9)]


@pytest.fixture
def events():
    repository = InMemoryEventRepository()
    categories = {"Партер": PriceCategory("Партер", Money(Decimal("600")))}
    seats = {position: Seat(position, "Партер") for position in SEATS}
    repository.save(Event(EVENT_ID, "Концерт", NOW - timedelta(days=1), categories, seats))
    return repository


@pytest.fixture
def orders():
    return InMemoryOrderRepository()


@pytest.fixture
def reserve_seats(events, orders):
    return ReserveSeats(events, InMemoryReservationRepository(), orders, clock=lambda: NOW)


def command(*numbers):
    return ReserveSeatsCommand(EVENT_ID, BUYER_ID, tuple(("Партер", 1, n) for n in numbers))


def test_reservation_is_saved_and_order_total_is_returned(reserve_seats, events, orders):
    result = reserve_seats.execute(command(1, 2))

    assert result.total_amount == Decimal("1200")
    assert result.pay_until == NOW + timedelta(minutes=15)
    assert events.get(EVENT_ID).seats[SEATS[0]].status is SeatStatus.RESERVED
    assert orders.get(result.order_id).total == Money(Decimal("1200"))


def test_failed_reservation_leaves_storage_unchanged(reserve_seats, events):
    reserve_seats.execute(command(2))

    with pytest.raises(SeatNotAvailableError):
        reserve_seats.execute(command(1, 2))

    assert events.get(EVENT_ID).seats[SEATS[0]].status is SeatStatus.AVAILABLE


def test_buyer_cannot_exceed_six_seats_across_reservations(reserve_seats, events):
    reserve_seats.execute(command(1, 2, 3, 4))

    with pytest.raises(ReservationLimitError):
        reserve_seats.execute(command(5, 6, 7))

    assert events.get(EVENT_ID).seats[SEATS[4]].status is SeatStatus.AVAILABLE
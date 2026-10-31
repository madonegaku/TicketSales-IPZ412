"""Тести репозиторіїв у пам'яті: відповідність контракту доменних інтерфейсів."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from ticketing.domain.event import Event, PriceCategory, Seat, SeatStatus
from ticketing.domain.exceptions import NotFoundError
from ticketing.domain.reservation import Reservation
from ticketing.domain.value_objects import Money, SeatPosition
from ticketing.infrastructure.in_memory import (
    InMemoryEventRepository,
    InMemoryReservationRepository,
)

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
A1 = SeatPosition("Партер", 1, 1)


def make_event():
    categories = {"Партер": PriceCategory("Партер", Money(Decimal("600")))}
    return Event(uuid4(), "Концерт", NOW, categories, {A1: Seat(A1, "Партер")})


def test_changes_are_not_stored_without_save():
    repository = InMemoryEventRepository()
    event = make_event()
    repository.save(event)

    loaded = repository.get(event.id)
    loaded.reserve_seats([A1], now=NOW)

    assert repository.get(event.id).seats[A1].status is SeatStatus.AVAILABLE


def test_saved_changes_are_returned_by_get():
    repository = InMemoryEventRepository()
    event = make_event()
    event.reserve_seats([A1], now=NOW)

    repository.save(event)

    assert repository.get(event.id).seats[A1].status is SeatStatus.RESERVED


def test_missing_event_raises_not_found():
    with pytest.raises(NotFoundError):
        InMemoryEventRepository().get(uuid4())


def test_count_seats_held_ignores_expired_reservations_and_other_buyers():
    repository = InMemoryReservationRepository()
    buyer_id, event_id = uuid4(), uuid4()
    positions = [SeatPosition("Партер", 1, number) for number in range(1, 4)]
    repository.save(Reservation.create(event_id, buyer_id, positions[:2], NOW, 0))
    repository.save(Reservation.create(event_id, uuid4(), positions[2:], NOW, 0))
    repository.save(
        Reservation.create(event_id, buyer_id, positions[2:], NOW - timedelta(minutes=20), 0)
    )

    assert repository.count_seats_held(buyer_id, event_id, NOW) == 2
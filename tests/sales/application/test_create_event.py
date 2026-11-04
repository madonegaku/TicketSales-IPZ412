"""Сценарій CreateEvent: захід організатора будується EventBuilder; некоректна схема залу відхиляється."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from sales.application.create_event import CreateEvent, CreateEventCommand, SectorSpec
from sales.domain.event import SeatStatus
from sales.domain.exceptions import InvalidEventError
from sales.domain.value_objects import SeatPosition
from sales.infrastructure.in_memory import InMemoryEventRepository, InMemoryUnitOfWork

NOW = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)
ORGANIZER = uuid4()


def command(**changes):
    values = dict(
        organizer_id=ORGANIZER, title="  Вечір джазу ", sales_start=NOW, starts_at=NOW + timedelta(days=30),
        categories=(("Партер", Decimal("800"), "UAH"), ("Балкон", Decimal("350"), "UAH")),
        sectors=(SectorSpec("Партер", 2, 3, "Партер"), SectorSpec("Балкон", 1, 2, "Балкон")),
    )
    return CreateEventCommand(**{**values, **changes})


def test_event_is_created_for_organizer_with_all_seats_free():
    events = InMemoryEventRepository()

    event_id = CreateEvent(events, InMemoryUnitOfWork()).execute(command())

    event = events.get(event_id)
    assert (event.title, event.organizer_id, len(event.seats)) == ("Вечір джазу", ORGANIZER, 8)
    assert list(event.seats)[0] == SeatPosition("Партер", 1, 1), "порядок місць – як задав організатор"
    assert {seat.status for seat in event.seats.values()} == {SeatStatus.AVAILABLE}


@pytest.mark.parametrize(
    "changes",
    [
        {"sectors": ()},
        {"sectors": tuple(SectorSpec(f"С{i}", 1, 1, "Партер") for i in range(11))},
        {"sectors": (SectorSpec("Партер", 51, 1, "Партер"),)},
        {"sectors": (SectorSpec("Партер", 1, 61, "Партер"),)},
        {"sectors": (SectorSpec("Партер", 1, 2, "Партер"), SectorSpec("Партер", 1, 2, "Партер"))},
        {"starts_at": NOW},
        {"title": "   "},
    ],
    ids=["no-sectors", "too-many-sectors", "too-many-rows", "too-many-seats", "duplicate-sector", "starts-at-sales",
         "empty-title"],
)
def test_invalid_hall_is_rejected_and_nothing_is_saved(changes):
    events = InMemoryEventRepository()

    with pytest.raises(InvalidEventError):
        CreateEvent(events, InMemoryUnitOfWork()).execute(command(**changes))

    assert events.list_all() == []

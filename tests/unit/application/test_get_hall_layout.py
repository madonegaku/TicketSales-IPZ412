"""Тести запиту GetHallLayout на демонстраційних даних."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from ticketing.application.get_hall_layout import GetHallLayout
from ticketing.application.reserve_seats import ReserveSeats, ReserveSeatsCommand
from ticketing.infrastructure.demo_data import DEMO_EVENT_ID, seed_demo_event
from ticketing.infrastructure.in_memory import (
    InMemoryEventRepository,
    InMemoryOrderRepository,
    InMemoryReservationRepository,
)

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


def test_hall_layout_shows_prices_and_reserved_seats():
    events = InMemoryEventRepository()
    seed_demo_event(events)
    reserve_seats = ReserveSeats(
        events, InMemoryReservationRepository(), InMemoryOrderRepository(), lambda: NOW
    )
    reserve_seats.execute(ReserveSeatsCommand(DEMO_EVENT_ID, uuid4(), (("VIP", 1, 1),)))

    layout = GetHallLayout(events).execute(DEMO_EVENT_ID)
    seats = {(seat.sector, seat.row, seat.number): seat for seat in layout.seats}

    assert len(layout.seats) == 56
    assert seats[("VIP", 1, 1)].is_available is False
    assert seats[("VIP", 1, 2)].is_available is True
    assert seats[("Партер", 3, 7)].price == Decimal("600")
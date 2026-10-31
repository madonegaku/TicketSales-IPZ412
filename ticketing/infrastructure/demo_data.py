"""Демонстраційні дані для ЛР 2: один захід зі схемою залу (у ЛР 5 – з бази даних)."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from ticketing.domain.event import Event, PriceCategory, Seat
from ticketing.domain.repositories import EventRepository
from ticketing.domain.value_objects import Money, SeatPosition

DEMO_EVENT_ID = UUID("00000000-0000-0000-0000-000000000018")


def seed_demo_event(events: EventRepository) -> None:
    """Додає концерт: партер 5 рядів по 10 місць (600 грн) і VIP 1 ряд з 6 місць (1500 грн)."""
    categories = {
        "Партер": PriceCategory("Партер", Money(Decimal("600"))),
        "VIP": PriceCategory("VIP", Money(Decimal("1500"))),
    }
    seats = {}
    for row in range(1, 6):
        for number in range(1, 11):
            position = SeatPosition("Партер", row, number)
            seats[position] = Seat(position, "Партер")
    for number in range(1, 7):
        position = SeatPosition("VIP", 1, number)
        seats[position] = Seat(position, "VIP")

    sales_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    events.save(Event(DEMO_EVENT_ID, "Концерт симфонічного оркестру", sales_start, categories, seats))
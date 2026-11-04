"""Демонстраційні дані: один захід зі схемою залу."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sales.domain.event_builder import EventBuilder
from sales.domain.exceptions import NotFoundError
from sales.domain.repositories import EventRepository
from sales.domain.value_objects import Money

DEMO_EVENT_ID = UUID("00000000-0000-0000-0000-000000000018")


def seed_demo_event(events: EventRepository) -> None:
    """Додає концерт: партер 5 рядів по 10 місць (600 грн) і VIP 1 ряд з 6 місць (1500 грн)."""
    event = (
        EventBuilder(DEMO_EVENT_ID, "Концерт симфонічного оркестру")
        .sales_start(datetime(2026, 1, 1, tzinfo=timezone.utc))
        .starts_at(datetime(2026, 12, 20, 17, 0, tzinfo=timezone.utc))
        .category("Партер", Money(Decimal("600")))
        .category("VIP", Money(Decimal("1500")))
        .seats("Партер", rows=range(1, 6), numbers=range(1, 11))
        .seats("VIP", rows=[1], numbers=range(1, 7))
        .build()
    )
    events.save(event)


def ensure_demo_event(events: EventRepository) -> None:
    """Додає демо-захід лише тоді, коли його ще немає.

    Сховище в PostgreSQL переживає перезапуск sales: повторне seed_demo_event() перезаписало
    б стан місць і «звільнило» б уже продані місця.
    """
    try:
        events.get(DEMO_EVENT_ID)
    except NotFoundError:
        seed_demo_event(events)

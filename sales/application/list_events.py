"""Запит «Афіша»: заходи з кількістю вільних місць і найнижчою ціною."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sales.domain.event import Event, SeatStatus
from sales.domain.repositories import EventRepository


@dataclass(frozen=True)
class EventSummary:
    """Захід у списку афіші."""

    event_id: UUID
    title: str
    sales_start: datetime
    starts_at: datetime
    seats_total: int
    seats_available: int
    price_from: Decimal
    currency: str


def summary_of(event: Event) -> EventSummary:
    cheapest = min((category.price for category in event.categories.values()), key=lambda price: price.amount)
    available = sum(1 for seat in event.seats.values() if seat.status is SeatStatus.AVAILABLE)
    return EventSummary(
        event.id, event.title, event.sales_start, event.starts_at, len(event.seats), available,
        cheapest.amount, cheapest.currency,
    )


class ListEvents:
    """Повертає афішу – усі заходи за часом початку; стан сховища не змінює."""

    def __init__(self, events: EventRepository) -> None:
        self._events = events

    def execute(self) -> list[EventSummary]:
        return [summary_of(event) for event in self._events.list_all()]

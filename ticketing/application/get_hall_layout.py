"""Запит «Схема залу»: місця заходу зі статусами та цінами для сторінки вибору."""

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from ticketing.domain.event import SeatStatus
from ticketing.domain.repositories import EventRepository


@dataclass(frozen=True)
class SeatView:
    """Місце на схемі залу в тому вигляді, який потрібен для відображення."""

    sector: str
    row: int
    number: int
    category: str
    price: Decimal
    currency: str
    is_available: bool


@dataclass(frozen=True)
class HallLayout:
    """Вихідні дані: захід і всі його місця."""

    event_id: UUID
    title: str
    seats: tuple[SeatView, ...]


class GetHallLayout:
    """Повертає схему залу заходу; стан сховища не змінює."""

    def __init__(self, events: EventRepository) -> None:
        self._events = events

    def execute(self, event_id: UUID) -> HallLayout:
        event = self._events.get(event_id)
        seats = []
        for seat in event.seats.values():
            price = event.price_of(seat.position)
            seats.append(
                SeatView(
                    seat.position.sector,
                    seat.position.row,
                    seat.position.number,
                    seat.category,
                    price.amount,
                    price.currency,
                    seat.status is SeatStatus.AVAILABLE,
                )
            )
        return HallLayout(event.id, event.title, tuple(seats))
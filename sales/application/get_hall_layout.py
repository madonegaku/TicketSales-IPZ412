"""Запит «Схема залу»: місця заходу зі статусами та цінами для сторінки вибору; кеш результату."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sales.domain.event import SeatStatus
from sales.domain.repositories import EventRepository


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


class HallLayoutCache(ABC):
    """Кеш схеми залу – найчастішого сценарію читання (С-01).

    Що кешується: HallLayout – результат цього запиту. Ключ: ідентифікатор заходу.
    Інвалідизація – подією: сценарії, що змінюють стан місць (ReserveSeats, PayOrder),
    видаляють запис після фіксації транзакції. Час життя запису – страховка, що обмежує
    застарілість, якщо видалення не відбулося (кеш недоступний, гонитва читання із записом).
    Промах: читання зі сховища й запис у кеш. Збої кешу не повинні ламати сценарії.

    Інтерфейс – у шарі застосунку, бо коли запис стає недійсним, знають лише сценарії;
    реалізації (Redis, без кешу) – в інфраструктурі.
    """

    @abstractmethod
    def get(self, event_id: UUID) -> HallLayout | None:
        """Збережена схема залу або None (промах, запис прострочений чи кеш недоступний)."""

    @abstractmethod
    def put(self, layout: HallLayout) -> None:
        """Зберігає схему залу на час життя запису."""

    @abstractmethod
    def invalidate(self, event_id: UUID) -> None:
        """Робить запис недійсним: стан місць заходу змінився."""


class GetHallLayout:
    """Повертає схему залу заходу; стан сховища не змінює.

    Спершу кеш; за промаху – захід зі сховища, і результат кладеться в кеш.
    """

    def __init__(self, events: EventRepository, cache: HallLayoutCache) -> None:
        self._events = events
        self._cache = cache

    def execute(self, event_id: UUID) -> HallLayout:
        cached = self._cache.get(event_id)
        if cached is not None:
            return cached
        layout = self._load(event_id)
        self._cache.put(layout)
        return layout

    def _load(self, event_id: UUID) -> HallLayout:
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

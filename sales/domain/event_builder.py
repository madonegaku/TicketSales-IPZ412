"""Покрокове створення заходу зі схемою залу (патерн Builder).

Конструктор Event приймає готові словники categories і seats, ключі яких мають збігатися з
ідентичністю самих об'єктів (назва категорії, позиція місця), а місця залу зазвичай задаються
вкладеними циклами за рядами й номерами. Будівник бере ці деталі на себе: ключі формуються
автоматично, ряди й номери задаються діапазонами, порядок місць зберігається.
"""

from collections.abc import Iterable
from datetime import datetime
from uuid import UUID

from sales.domain.event import Event, PriceCategory, Seat
from sales.domain.value_objects import Money, SeatPosition


class EventBuilder:
    """Будівник заходу: EventBuilder(id, назва).sales_start(…).starts_at(…).category(…).seats(…).build()."""

    def __init__(self, event_id: UUID, title: str) -> None:
        self._event_id = event_id
        self._title = title
        self._sales_start: datetime | None = None
        self._starts_at: datetime | None = None
        self._categories: dict[str, PriceCategory] = {}
        self._seats: dict[SeatPosition, Seat] = {}

    def sales_start(self, moment: datetime) -> "EventBuilder":
        self._sales_start = moment
        return self

    def starts_at(self, moment: datetime) -> "EventBuilder":
        self._starts_at = moment
        return self

    def category(self, name: str, price: Money) -> "EventBuilder":
        """Цінова категорія; ключ у словнику категорій – її назва."""
        self._categories[name] = PriceCategory(name, price)
        return self

    def seats(
        self, sector: str, rows: Iterable[int], numbers: Iterable[int], category: str | None = None
    ) -> "EventBuilder":
        """Місця сектору ряд за рядом; категорія за замовчуванням має назву сектору."""
        numbers = list(numbers)
        for row in rows:
            for number in numbers:
                position = SeatPosition(sector, row, number)
                if position in self._seats:
                    raise ValueError(f"Місце {position} уже додано до схеми залу.")
                self._seats[position] = Seat(position, category or sector)
        return self

    def build(self) -> Event:
        """Створює захід; інваріанти Event (відома категорія кожного місця) перевіряє сам Event."""
        if self._sales_start is None or self._starts_at is None:
            raise ValueError("Для заходу потрібно задати старт продажу й час початку.")
        return Event(
            self._event_id, self._title, self._sales_start, dict(self._categories), dict(self._seats), self._starts_at
        )

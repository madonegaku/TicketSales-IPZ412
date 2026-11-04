"""Сценарій «Створити захід»: організатор задає назву, дати, цінові категорії й сектори залу."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sales.application.unit_of_work import UnitOfWork
from sales.domain.event_builder import EventBuilder
from sales.domain.exceptions import InvalidEventError
from sales.domain.repositories import EventRepository
from sales.domain.value_objects import Money

MAX_SECTORS = 10
MAX_ROWS = 50
MAX_SEATS_PER_ROW = 60


@dataclass(frozen=True)
class SectorSpec:
    """Сектор залу: ряди 1..rows, у кожному місця 1..seats_per_row, ціна – цінової категорії price_category."""

    name: str
    rows: int
    seats_per_row: int
    price_category: str


@dataclass(frozen=True)
class CreateEventCommand:
    organizer_id: UUID
    title: str
    sales_start: datetime
    starts_at: datetime
    categories: tuple[tuple[str, Decimal, str], ...]
    sectors: tuple[SectorSpec, ...]


class CreateEvent:
    """Створює захід організатора за допомогою EventBuilder (ЛР 4).

    Розміри залу обмежено, щоб помилка у формі не створила захід на мільйон місць; інваріанти
    самого заходу (є місця, початок після старту продажу, відомі категорії) перевіряє Event.
    """

    def __init__(self, events: EventRepository, unit_of_work: UnitOfWork) -> None:
        self._events = events
        self._unit_of_work = unit_of_work

    def execute(self, command: CreateEventCommand) -> UUID:
        if not 1 <= len(command.sectors) <= MAX_SECTORS:
            raise InvalidEventError(f"Захід має містити від 1 до {MAX_SECTORS} секторів.")
        builder = (
            EventBuilder(uuid4(), command.title.strip())
            .organizer(command.organizer_id)
            .sales_start(command.sales_start)
            .starts_at(command.starts_at)
        )
        for name, amount, currency in command.categories:
            builder.category(name.strip(), Money(amount, currency))
        for sector in command.sectors:
            if not (1 <= sector.rows <= MAX_ROWS and 1 <= sector.seats_per_row <= MAX_SEATS_PER_ROW):
                raise InvalidEventError(
                    f"Сектор «{sector.name}»: від 1 до {MAX_ROWS} рядів і від 1 до {MAX_SEATS_PER_ROW} місць у ряду."
                )
            try:
                builder.seats(sector.name.strip(), rows=range(1, sector.rows + 1),
                              numbers=range(1, sector.seats_per_row + 1), category=sector.price_category.strip())
            except ValueError as exc:
                raise InvalidEventError(str(exc)) from exc
        event = builder.build()
        with self._unit_of_work.transaction():
            self._events.save(event)
        return event.id

"""Агрегат «Захід»: захід, його цінові категорії та місця."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID

from sales.domain.exceptions import (
    InvalidEventError,
    InvalidSeatSelectionError,
    InvalidSeatTransitionError,
    SalesNotStartedError,
    SeatNotAvailableError,
    UnknownPriceCategoryError,
)
from sales.domain.value_objects import Money, SeatPosition


class SeatStatus(Enum):
    """Стан місця на конкретному заході."""

    AVAILABLE = "вільне"
    RESERVED = "зарезервоване"
    SOLD = "продане"


@dataclass(eq=False)
class Seat:
    """Місце на конкретному заході – сутність усередині агрегату Event.

    Ідентичність – позиція в схемі залу в межах заходу. Дозволені переходи:
    вільне → зарезервоване → продане; зарезервоване → вільне (резервування
    прострочене чи скасоване); продане → вільне (повернення квитка).
    """

    position: SeatPosition
    category: str
    status: SeatStatus = SeatStatus.AVAILABLE

    def reserve(self) -> None:
        if self.status is not SeatStatus.AVAILABLE:
            raise SeatNotAvailableError(f"Місце {self.position} вже зайняте.")
        self.status = SeatStatus.RESERVED

    def sell(self) -> None:
        if self.status is not SeatStatus.RESERVED:
            raise InvalidSeatTransitionError("Продати можна лише зарезервоване місце.")
        self.status = SeatStatus.SOLD

    def release(self) -> None:
        if self.status is SeatStatus.AVAILABLE:
            raise InvalidSeatTransitionError("Місце вже вільне.")
        self.status = SeatStatus.AVAILABLE


@dataclass(eq=False)
class PriceCategory:
    """Цінова категорія заходу – сутність усередині агрегату Event.

    Ідентичність – назва категорії в межах заходу (наприклад, «Партер»).
    """

    name: str
    price: Money


@dataclass(eq=False)
class Event:
    """Захід – корінь агрегату: єдина точка зміни стану своїх місць.

    starts_at – час початку заходу; у ЛР 3 передається сервісу tickets у події OrderPaid.
    organizer_id – організатор, який створив захід (ADR-006); у демо-заходу ЛР 2 – немає.
    Інваріанти: є хоча б одне місце; захід починається пізніше за старт продажу; кожне місце
    належить до однієї з цінових категорій заходу; одне місце не може бути зарезервоване чи
    продане двічі (С-03).
    """

    id: UUID
    title: str
    sales_start: datetime
    categories: dict[str, PriceCategory]
    seats: dict[SeatPosition, Seat]
    starts_at: datetime
    organizer_id: UUID | None = None

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise InvalidEventError("Назва заходу не може бути порожньою.")
        if not self.seats:
            raise InvalidEventError("У заході має бути хоча б одне місце.")
        if self.starts_at <= self.sales_start:
            raise InvalidEventError("Захід має починатися пізніше за старт продажу.")
        for seat in self.seats.values():
            if seat.category not in self.categories:
                raise UnknownPriceCategoryError(
                    f"Місце {seat.position} належить до невідомої категорії «{seat.category}»."
                )

    def reserve_seats(self, positions: list[SeatPosition], now: datetime) -> None:
        """Резервує всі обрані місця або жодне."""
        if now < self.sales_start:
            raise SalesNotStartedError("Продаж квитків на цей захід ще не розпочався.")
        seats = self._find_seats(positions)
        for seat in seats:
            if seat.status is not SeatStatus.AVAILABLE:
                raise SeatNotAvailableError(f"Місце {seat.position} вже зайняте.")
        for seat in seats:
            seat.reserve()

    def sell_seats(self, positions: list[SeatPosition]) -> None:
        """Продає всі зарезервовані місця замовлення або жодне."""
        seats = self._find_seats(positions)
        for seat in seats:
            if seat.status is not SeatStatus.RESERVED:
                raise InvalidSeatTransitionError(f"Місце {seat.position} не зарезервоване.")
        for seat in seats:
            seat.sell()

    def price_of(self, position: SeatPosition) -> Money:
        seat = self._find_seats([position])[0]
        return self.categories[seat.category].price

    def _find_seats(self, positions: list[SeatPosition]) -> list[Seat]:
        if len(set(positions)) != len(positions):
            raise InvalidSeatSelectionError("Одне місце обрано кілька разів.")
        for position in positions:
            if position not in self.seats:
                raise InvalidSeatSelectionError(f"Місця {position} немає в схемі залу.")
        return [self.seats[position] for position in positions]
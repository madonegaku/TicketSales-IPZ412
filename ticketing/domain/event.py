"""Агрегат «Захід»: захід, його цінові категорії та місця."""

from dataclasses import dataclass
from enum import Enum

from ticketing.domain.exceptions import InvalidSeatTransitionError, SeatNotAvailableError
from ticketing.domain.value_objects import SeatPosition


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
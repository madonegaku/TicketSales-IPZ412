"""Оплачене замовлення в розумінні tickets: локальна копія даних із події OrderPaid."""

from dataclasses import dataclass
from uuid import UUID

from tickets.domain.exceptions import InvalidPaidOrderError
from tickets.domain.value_objects import SeatPosition


@dataclass(frozen=True)
class PaidOrder:
    """Замовлення, за яке вже надійшла оплата; tickets знає лише те, що потрібне для видачі квитків.

    Інваріанти: хоча б одне місце; місця не повторюються. Ліміт 6 місць – правило sales,
    тут він не перевіряється (його гарантує контракт події).
    """

    order_id: UUID
    event_id: UUID
    positions: tuple[SeatPosition, ...]

    def __post_init__(self) -> None:
        if not self.positions:
            raise InvalidPaidOrderError("Оплачене замовлення має містити хоча б одне місце.")
        if len(set(self.positions)) != len(self.positions):
            raise InvalidPaidOrderError("Місце в замовленні повторюється.")
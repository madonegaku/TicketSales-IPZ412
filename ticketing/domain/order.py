"""Замовлення: оплата зарезервованих місць."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from ticketing.domain.event import Event
from ticketing.domain.exceptions import (
    InvalidOrderError,
    OrderAlreadyPaidError,
    ReservationExpiredError,
)
from ticketing.domain.reservation import Reservation
from ticketing.domain.value_objects import Money, SeatPosition


class OrderStatus(Enum):
    """Стан замовлення."""

    AWAITING_PAYMENT = "очікує оплати"
    PAYMENT_PENDING = "оплата в обробці"
    PAID = "оплачене"


@dataclass(frozen=True)
class OrderLine:
    """Рядок замовлення: місце та ціна, зафіксована в момент резервування."""

    position: SeatPosition
    price: Money


@dataclass(eq=False)
class Order:
    """Замовлення – окремий агрегат, посилається на резервування за ідентифікатором.

    Інваріанти: містить хоча б один рядок; сума – це сума цін рядків;
    оплату можна розпочати лише до кінця строку резервування (С-04);
    підтвердити оплату можна лише один раз (С-05).
    """

    id: UUID
    reservation_id: UUID
    lines: tuple[OrderLine, ...]
    payment_deadline: datetime
    status: OrderStatus = OrderStatus.AWAITING_PAYMENT

    def __post_init__(self) -> None:
        if not self.lines:
            raise InvalidOrderError("Замовлення має містити хоча б одне місце.")

    @classmethod
    def for_reservation(cls, reservation: Reservation, event: Event) -> "Order":
        """Створює замовлення з цінами місць, зафіксованими на момент резервування."""
        if reservation.event_id != event.id:
            raise InvalidOrderError("Резервування належить до іншого заходу.")
        lines = tuple(
            OrderLine(position, event.price_of(position)) for position in reservation.positions
        )
        return cls(uuid4(), reservation.id, lines, reservation.expires_at)

    @property
    def total(self) -> Money:
        first, *rest = self.lines
        return sum((line.price for line in rest), start=first.price)

    def start_payment(self, now: datetime) -> None:
        """Розпочинає оплату, якщо строк резервування ще не минув (С-04)."""
        self._ensure_not_paid()
        if self.status is not OrderStatus.AWAITING_PAYMENT:
            raise InvalidOrderError("Оплата цього замовлення вже розпочата.")
        if now >= self.payment_deadline:
            raise ReservationExpiredError("Строк резервування минув – оберіть місця знову.")
        self.status = OrderStatus.PAYMENT_PENDING

    def confirm_payment(self) -> None:
        """Підтверджує оплату один раз; час уже не перевіряється (С-04, С-05)."""
        self._ensure_not_paid()
        if self.status is not OrderStatus.PAYMENT_PENDING:
            raise InvalidOrderError("Не можна підтвердити оплату, яку не розпочато.")
        self.status = OrderStatus.PAID

    def _ensure_not_paid(self) -> None:
        if self.status is OrderStatus.PAID:
            raise OrderAlreadyPaidError("Замовлення вже оплачене.")
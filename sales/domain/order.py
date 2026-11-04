"""Замовлення: оплата зарезервованих місць."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from sales.domain.event import Event
from sales.domain.exceptions import (
    InvalidOrderError,
    OrderAlreadyPaidError,
    ReservationExpiredError,
)
from sales.domain.order_state import OrderStatus
from sales.domain.reservation import Reservation
from sales.domain.value_objects import Money, SeatPosition


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
    event_id: UUID
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
        return cls(uuid4(), reservation.id, event.id, lines, reservation.expires_at)

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

    def start_or_resume_payment(self, now: datetime) -> None:
        """Розпочинає оплату або продовжує вже розпочату – повтор після збою платіжного сервісу (С-04)."""
        if self.status is OrderStatus.PAYMENT_PENDING:
            return
        self.start_payment(now)

    def cancel_payment(self) -> None:
        """Компенсація: банк відхилив оплату – замовлення знову очікує оплати до кінця резервування."""
        if self.status is not OrderStatus.PAYMENT_PENDING:
            raise InvalidOrderError("Скасувати можна лише розпочату й незавершену оплату.")
        self.status = OrderStatus.AWAITING_PAYMENT

    def confirm_payment(self) -> None:
        """Підтверджує оплату один раз; час уже не перевіряється (С-04, С-05)."""
        self._ensure_not_paid()
        if self.status is not OrderStatus.PAYMENT_PENDING:
            raise InvalidOrderError("Не можна підтвердити оплату, яку не розпочато.")
        self.status = OrderStatus.PAID

    def _ensure_not_paid(self) -> None:
        if self.status is OrderStatus.PAID:
            raise OrderAlreadyPaidError("Замовлення вже оплачене.")
"""Замовлення: оплата зарезервованих місць."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from sales.domain.event import Event
from sales.domain.exceptions import InvalidOrderError
from sales.domain.order_state import OrderStatus, state_of
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

    Які операції оплати дозволені в поточному стані, вирішує об'єкт стану
    (sales/domain/order_state.py, патерн State); Order лише зберігає status.
    """

    id: UUID
    reservation_id: UUID
    event_id: UUID
    buyer_id: UUID
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
        return cls(uuid4(), reservation.id, event.id, reservation.buyer_id, lines, reservation.expires_at)

    def belongs_to(self, buyer_id: UUID) -> bool:
        """Чи належить замовлення покупцю: оплатити й переглянути його може лише власник."""
        return self.buyer_id == buyer_id

    @property
    def total(self) -> Money:
        first, *rest = self.lines
        return sum((line.price for line in rest), start=first.price)

    def start_payment(self, now: datetime) -> None:
        """Розпочинає оплату, якщо строк резервування ще не минув (С-04)."""
        self.status = state_of(self.status).start_payment(self.payment_deadline, now)

    def start_or_resume_payment(self, now: datetime) -> None:
        """Розпочинає оплату або продовжує вже розпочату – повтор після збою платіжного сервісу (С-04)."""
        self.status = state_of(self.status).resume_payment(self.payment_deadline, now)

    def cancel_payment(self) -> None:
        """Компенсація: банк відхилив оплату – замовлення знову очікує оплати до кінця резервування."""
        self.status = state_of(self.status).cancel_payment()

    def confirm_payment(self) -> None:
        """Підтверджує оплату один раз; час уже не перевіряється (С-04, С-05)."""
        self.status = state_of(self.status).confirm_payment()

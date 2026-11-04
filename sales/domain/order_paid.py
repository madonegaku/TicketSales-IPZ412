"""Доменна подія «Замовлення оплачено» – факт, про який sales повідомляє інші сервіси."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from sales.domain.event import Event
from sales.domain.exceptions import InvalidOrderError
from sales.domain.order import Order, OrderStatus
from sales.domain.value_objects import SeatPosition


@dataclass(frozen=True)
class OrderPaid:
    """Подія про оплату замовлення; поля відповідають контракту contracts/order-paid.asyncapi.yaml (v1).

    Інваріант: створюється лише для оплаченого замовлення свого заходу.
    """

    message_id: UUID
    occurred_at: datetime
    order_id: UUID
    event_id: UUID
    event_title: str
    event_starts_at: datetime
    seats: tuple[SeatPosition, ...]

    @classmethod
    def for_order(cls, order: Order, event: Event, now: datetime) -> "OrderPaid":
        if order.status is not OrderStatus.PAID:
            raise InvalidOrderError("Подію OrderPaid можна створити лише для оплаченого замовлення.")
        if order.event_id != event.id:
            raise InvalidOrderError("Замовлення належить до іншого заходу.")
        seats = tuple(line.position for line in order.lines)
        return cls(uuid4(), now, order.id, event.id, event.title, event.starts_at, seats)
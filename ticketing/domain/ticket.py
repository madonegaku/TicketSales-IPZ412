"""Квиток: право відвідати захід на конкретному місці."""

import secrets
from dataclasses import dataclass
from enum import Enum
from uuid import UUID, uuid4

from ticketing.domain.exceptions import (
    InvalidTicketError,
    OrderNotPaidError,
    TicketAlreadyUsedError,
)
from ticketing.domain.order import Order, OrderStatus
from ticketing.domain.value_objects import SeatPosition


class TicketStatus(Enum):
    """Стан квитка."""

    VALID = "дійсний"
    USED = "використаний"
    REFUNDED = "повернений"


@dataclass(eq=False)
class Ticket:
    """Квиток – окремий агрегат; код для QR унікальний і непередбачуваний.

    Інваріанти: видається лише за оплаченим замовленням; валідується лише дійсний
    квиток свого заходу, після валідації стає використаним і повторно не приймається
    (С-07); повернути можна лише дійсний квиток.
    """

    id: UUID
    order_id: UUID
    event_id: UUID
    position: SeatPosition
    code: str
    status: TicketStatus = TicketStatus.VALID

    @classmethod
    def issue_for(cls, order: Order) -> list["Ticket"]:
        """Видає по квитку на кожне місце оплаченого замовлення."""
        if order.status is not OrderStatus.PAID:
            raise OrderNotPaidError("Квитки видаються лише за оплаченим замовленням.")
        return [
            cls(uuid4(), order.id, order.event_id, line.position, secrets.token_urlsafe(16))
            for line in order.lines
        ]

    def validate(self, event_id: UUID) -> None:
        """Пропускає відвідувача на захід: квиток стає використаним (С-07)."""
        if self.event_id != event_id:
            raise InvalidTicketError("Квиток виданий на інший захід.")
        if self.status is TicketStatus.USED:
            raise TicketAlreadyUsedError("Квиток уже використано – повторний вхід заборонено.")
        if self.status is TicketStatus.REFUNDED:
            raise InvalidTicketError("Квиток повернено – він недійсний.")
        self.status = TicketStatus.USED

    def refund(self) -> None:
        """Анулює дійсний квиток; використаний повернути не можна."""
        if self.status is not TicketStatus.VALID:
            raise InvalidTicketError("Повернути можна лише дійсний невикористаний квиток.")
        self.status = TicketStatus.REFUNDED
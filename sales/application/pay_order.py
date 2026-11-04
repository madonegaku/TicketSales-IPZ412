"""Сценарій «Оплата замовлення»: оплата й продаж місць. Квитки видає сервіс tickets."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sales.domain.payment_gateway import PaymentGateway
from sales.domain.repositories import EventRepository, OrderRepository


@dataclass(frozen=True)
class PayOrderCommand:
    """Вхідні дані: замовлення, яке покупець оплачує."""

    order_id: UUID


@dataclass(frozen=True)
class PayOrderResult:
    """Вихідні дані: оплачене замовлення; квитки за ним видасть сервіс tickets."""

    order_id: UUID


class PayOrder:
    """Оплачує замовлення через платіжний шлюз і продає місця.

    Транзакційна межа: усе, що може порушити доменне правило, перевіряється
    до списання коштів, а збереження відбувається лише після успішної оплати
    (С-04). Видачу квитків у ЛР 3 перенесено в сервіс tickets (подія OrderPaid).
    """

    def __init__(
        self,
        events: EventRepository,
        orders: OrderRepository,
        payment_gateway: PaymentGateway,
        clock: Callable[[], datetime],
    ) -> None:
        self._events = events
        self._orders = orders
        self._payment_gateway = payment_gateway
        self._clock = clock

    def execute(self, command: PayOrderCommand) -> PayOrderResult:
        order = self._orders.get(command.order_id)
        event = self._events.get(order.event_id)

        order.start_payment(self._clock())
        event.sell_seats([line.position for line in order.lines])
        self._payment_gateway.charge(order.id, order.total)
        order.confirm_payment()

        self._orders.save(order)
        self._events.save(event)

        return PayOrderResult(order.id)
"""Сценарій «Оплата замовлення»: оплата й продаж місць. Квитки видає сервіс tickets."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from sales.domain.exceptions import PaymentDeclinedError

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
    """Оплачує замовлення через платіжний сервіс і продає місця.

    Порядок (С-04): спочатку зберігається намір – «оплата в обробці», лише потім синхронний
    виклик платіжного сервісу. Якщо він не відповів (PaymentUnavailableError), замовлення
    лишається в обробці, місця – зарезервованими, повтор безпечний. Якщо банк відхилив
    платіж – компенсація: замовлення знову очікує оплати. Квитки видає сервіс tickets.
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

        order.start_or_resume_payment(self._clock())
        event.sell_seats([line.position for line in order.lines])
        self._orders.save(order)

        try:
            self._payment_gateway.charge(order.id, order.total)
        except PaymentDeclinedError:
            order.cancel_payment()
            self._orders.save(order)
            raise

        order.confirm_payment()
        self._orders.save(order)
        self._events.save(event)

        return PayOrderResult(order.id)
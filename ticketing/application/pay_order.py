"""Сценарій «Оплата замовлення»: оплата, продаж місць і видача квитків."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from ticketing.domain.payment_gateway import PaymentGateway
from ticketing.domain.repositories import EventRepository, OrderRepository, TicketRepository
from ticketing.domain.ticket import Ticket


@dataclass(frozen=True)
class PayOrderCommand:
    """Вхідні дані: замовлення, яке покупець оплачує."""

    order_id: UUID


@dataclass(frozen=True)
class PayOrderResult:
    """Вихідні дані: коди квитків для QR."""

    order_id: UUID
    ticket_codes: tuple[str, ...]


class PayOrder:
    """Оплачує замовлення через платіжний шлюз, продає місця та видає квитки.

    Транзакційна межа: усе, що може порушити доменне правило, перевіряється
    до списання коштів, а збереження відбувається лише після успішної оплати
    (С-04). У ЛР 2 шлюз відповідає одразу; асинхронне підтвердження від LiqPay
    з'явиться разом зі справжньою реалізацією шлюзу.
    """

    def __init__(
        self,
        events: EventRepository,
        orders: OrderRepository,
        tickets: TicketRepository,
        payment_gateway: PaymentGateway,
        clock: Callable[[], datetime],
    ) -> None:
        self._events = events
        self._orders = orders
        self._tickets = tickets
        self._payment_gateway = payment_gateway
        self._clock = clock

    def execute(self, command: PayOrderCommand) -> PayOrderResult:
        order = self._orders.get(command.order_id)
        event = self._events.get(order.event_id)

        order.start_payment(self._clock())
        event.sell_seats([line.position for line in order.lines])
        self._payment_gateway.charge(order.id, order.total)
        order.confirm_payment()
        tickets = Ticket.issue_for(order)

        self._orders.save(order)
        self._events.save(event)
        for ticket in tickets:
            self._tickets.save(ticket)

        return PayOrderResult(order.id, tuple(ticket.code for ticket in tickets))
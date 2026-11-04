"""Сценарій «Оплата замовлення»: оплата й продаж місць. Про оплату повідомляє подією OrderPaid через вихідну чергу – квитки видає сервіс tickets."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sales.application.unit_of_work import UnitOfWork
from sales.domain.exceptions import PaymentDeclinedError
from sales.domain.order_paid import OrderPaid
from sales.domain.outbox import Outbox
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

    Три короткі транзакції замість однієї довгої: блокування бази не тримаються, поки триває
    мережевий виклик payments (до 2 с), інакше він зупинив би продаж на весь захід.
      1. Намір (С-04): замовлення → «оплата в обробці», перевірка, що місця ще зарезервовані.
      2. Виклик платіжного сервісу – поза транзакцією. Не відповів (PaymentUnavailableError) –
         замовлення лишається в обробці, повтор безпечний (ідемпотентність за order_id).
      3. Результат: відмова банку – компенсація (знову «очікує оплати»); успіх – замовлення
         оплачене, місця продані й подія OrderPaid у вихідній черзі – в одній транзакції.
    На кроці 3 замовлення й захід перечитуються з блокуванням: копія з кроку 1 могла застаріти
    (інші покупці резервували місця того самого заходу), і її збереження затерло б їхні зміни.
    """

    def __init__(
        self,
        events: EventRepository,
        orders: OrderRepository,
        payment_gateway: PaymentGateway,
        outbox: Outbox,
        clock: Callable[[], datetime],
        unit_of_work: UnitOfWork,
    ) -> None:
        self._events = events
        self._orders = orders
        self._payment_gateway = payment_gateway
        self._outbox = outbox
        self._clock = clock
        self._unit_of_work = unit_of_work

    def execute(self, command: PayOrderCommand) -> PayOrderResult:
        with self._unit_of_work.transaction():
            order = self._orders.get_for_update(command.order_id)
            event = self._events.get(order.event_id)
            order.start_or_resume_payment(self._clock())
            event.sell_seats([line.position for line in order.lines])
            self._orders.save(order)

        try:
            self._payment_gateway.charge(order.id, order.total)
        except PaymentDeclinedError:
            with self._unit_of_work.transaction():
                order = self._orders.get_for_update(command.order_id)
                order.cancel_payment()
                self._orders.save(order)
            raise

        with self._unit_of_work.transaction():
            order = self._orders.get_for_update(command.order_id)
            event = self._events.get_for_update(order.event_id)
            order.confirm_payment()
            event.sell_seats([line.position for line in order.lines])
            self._orders.save(order)
            self._events.save(event)
            self._outbox.add(OrderPaid.for_order(order, event, self._clock()))

        return PayOrderResult(order.id)

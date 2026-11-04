"""Запит «Мої замовлення»: замовлення покупця з назвою заходу, місцями, сумою й станом."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sales.domain.exceptions import NotFoundError
from sales.domain.order import Order
from sales.domain.repositories import EventRepository, OrderRepository


@dataclass(frozen=True)
class OrderSeatView:
    sector: str
    row: int
    number: int
    price: Decimal


@dataclass(frozen=True)
class OrderView:
    """Замовлення в тому вигляді, який потрібен покупцю. status – стабільний код (PAID), не текст."""

    order_id: UUID
    event_id: UUID
    event_title: str
    status: str
    total_amount: Decimal
    currency: str
    payment_deadline: datetime
    seats: tuple[OrderSeatView, ...]


class GetBuyerOrders:
    """Замовлення покупця; чуже замовлення для нього «не знайдене». Стан сховища не змінює."""

    def __init__(self, orders: OrderRepository, events: EventRepository) -> None:
        self._orders = orders
        self._events = events

    def execute(self, buyer_id: UUID) -> list[OrderView]:
        titles: dict[UUID, str] = {}
        return [self._view(order, titles) for order in self._orders.list_by_buyer(buyer_id)]

    def one(self, buyer_id: UUID, order_id: UUID) -> OrderView:
        order = self._orders.get(order_id)
        if not order.belongs_to(buyer_id):
            raise NotFoundError("Замовлення не знайдено.")
        return self._view(order, {})

    def _view(self, order: Order, titles: dict[UUID, str]) -> OrderView:
        if order.event_id not in titles:
            titles[order.event_id] = self._events.get(order.event_id).title
        total = order.total
        return OrderView(
            order.id, order.event_id, titles[order.event_id], order.status.name, total.amount, total.currency,
            order.payment_deadline,
            tuple(OrderSeatView(line.position.sector, line.position.row, line.position.number, line.price.amount)
                  for line in order.lines),
        )

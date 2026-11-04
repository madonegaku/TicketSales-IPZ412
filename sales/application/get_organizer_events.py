"""Запит «Мої заходи»: статистика продажу заходів організатора (адміністратор бачить усі)."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sales.domain.event import Event, SeatStatus
from sales.domain.order_state import OrderStatus
from sales.domain.repositories import EventRepository, OrderRepository


@dataclass(frozen=True)
class EventSalesView:
    """Захід зі станом продажу. Виручка – сума цін, зафіксованих в оплачених замовленнях."""

    event_id: UUID
    title: str
    sales_start: datetime
    starts_at: datetime
    organizer_id: UUID | None
    seats_total: int
    seats_available: int
    seats_reserved: int
    seats_sold: int
    paid_orders: int
    revenue: Decimal
    currency: str


class GetOrganizerEvents:
    """organizer_id = None – усі заходи (для адміністратора); стан сховища не змінює."""

    def __init__(self, events: EventRepository, orders: OrderRepository) -> None:
        self._events = events
        self._orders = orders

    def execute(self, organizer_id: UUID | None) -> list[EventSalesView]:
        events = self._events.list_all()
        if organizer_id is not None:
            events = [event for event in events if event.organizer_id == organizer_id]
        return [self._view(event) for event in events]

    def _view(self, event: Event) -> EventSalesView:
        statuses = [seat.status for seat in event.seats.values()]
        paid = [order for order in self._orders.list_by_event(event.id) if order.status is OrderStatus.PAID]
        currency = next(iter(event.categories.values())).price.currency
        revenue = sum((order.total.amount for order in paid), start=Decimal("0"))
        return EventSalesView(
            event.id, event.title, event.sales_start, event.starts_at, event.organizer_id, len(statuses),
            statuses.count(SeatStatus.AVAILABLE), statuses.count(SeatStatus.RESERVED), statuses.count(SeatStatus.SOLD),
            len(paid), revenue, currency,
        )

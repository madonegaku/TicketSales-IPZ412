"""Репозиторії в пам'яті – реалізації доменних інтерфейсів для ЛР 2.

Зберігають копії агрегатів, а не самі об'єкти: як і справжнє сховище, вони
бачать зміни лише після save(). У ЛР 5 їх замінять реалізації на Django ORM.
"""

from copy import deepcopy
from datetime import datetime
from uuid import UUID

from sales.domain.event import Event
from sales.domain.exceptions import NotFoundError
from sales.domain.order import Order
from sales.domain.repositories import (
    EventRepository,
    OrderRepository,
    ReservationRepository,
)
from sales.domain.reservation import Reservation


class InMemoryEventRepository(EventRepository):
    """Заходи у словнику за ідентифікатором."""

    def __init__(self) -> None:
        self._events: dict[UUID, Event] = {}

    def get(self, event_id: UUID) -> Event:
        if event_id not in self._events:
            raise NotFoundError("Захід не знайдено.")
        return deepcopy(self._events[event_id])

    def save(self, event: Event) -> None:
        self._events[event.id] = deepcopy(event)


class InMemoryReservationRepository(ReservationRepository):
    """Резервування у словнику за ідентифікатором."""

    def __init__(self) -> None:
        self._reservations: dict[UUID, Reservation] = {}

    def save(self, reservation: Reservation) -> None:
        self._reservations[reservation.id] = deepcopy(reservation)

    def count_seats_held(self, buyer_id: UUID, event_id: UUID, now: datetime) -> int:
        return sum(
            len(reservation.positions)
            for reservation in self._reservations.values()
            if reservation.buyer_id == buyer_id
            and reservation.event_id == event_id
            and not reservation.is_expired(now)
        )


class InMemoryOrderRepository(OrderRepository):
    """Замовлення у словнику за ідентифікатором."""

    def __init__(self) -> None:
        self._orders: dict[UUID, Order] = {}

    def get(self, order_id: UUID) -> Order:
        if order_id not in self._orders:
            raise NotFoundError("Замовлення не знайдено.")
        return deepcopy(self._orders[order_id])

    def save(self, order: Order) -> None:
        self._orders[order.id] = deepcopy(order)

"""Репозиторії в пам'яті – реалізації доменних інтерфейсів для ЛР 2.

Зберігають копії агрегатів, а не самі об'єкти: як і справжнє сховище, вони
бачать зміни лише після save(). У ЛР 5 їх замінять реалізації на Django ORM.
"""

from copy import deepcopy
from datetime import datetime
from uuid import UUID

from ticketing.domain.event import Event
from ticketing.domain.exceptions import NotFoundError
from ticketing.domain.order import Order
from ticketing.domain.repositories import (
    EventRepository,
    OrderRepository,
    ReservationRepository,
    TicketRepository,
)
from ticketing.domain.reservation import Reservation
from ticketing.domain.ticket import Ticket


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


class InMemoryTicketRepository(TicketRepository):
    """Квитки у словнику за кодом із QR."""

    def __init__(self) -> None:
        self._tickets: dict[str, Ticket] = {}

    def get_by_code(self, code: str) -> Ticket:
        if code not in self._tickets:
            raise NotFoundError("Квиток не знайдено.")
        return deepcopy(self._tickets[code])

    def save(self, ticket: Ticket) -> None:
        self._tickets[ticket.code] = deepcopy(ticket)
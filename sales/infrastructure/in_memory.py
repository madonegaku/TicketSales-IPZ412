"""Репозиторії в пам'яті – реалізації доменних інтерфейсів для ЛР 2.

Зберігають копії агрегатів, а не самі об'єкти: як і справжнє сховище, вони
бачать зміни лише після save(). У ЛР 5 робоча реалізація – PostgreSQL
(sales/infrastructure/postgres); ці лишаються для тестів сценаріїв і запуску без бази.
"""
import threading
from contextlib import AbstractContextManager, nullcontext
from copy import deepcopy
from datetime import datetime
from uuid import UUID

from sales.application.unit_of_work import UnitOfWork
from sales.domain.event import Event
from sales.domain.exceptions import NotFoundError
from sales.domain.order import Order
from sales.domain.order_paid import OrderPaid
from sales.domain.outbox import Outbox
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

    def list_all(self) -> list[Event]:
        return sorted((deepcopy(event) for event in self._events.values()), key=lambda event: event.starts_at)

    def get_for_update(self, event_id: UUID) -> Event:
        return self.get(event_id)

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

    def list_by_buyer(self, buyer_id: UUID) -> list[Order]:
        orders = [deepcopy(order) for order in self._orders.values() if order.buyer_id == buyer_id]
        return sorted(orders, key=lambda order: order.payment_deadline, reverse=True)

    def list_by_event(self, event_id: UUID) -> list[Order]:
        return [deepcopy(order) for order in self._orders.values() if order.event_id == event_id]

    def get_for_update(self, order_id: UUID) -> Order:
        return self.get(order_id)

    def save(self, order: Order) -> None:
        self._orders[order.id] = deepcopy(order)


class InMemoryUnitOfWork(UnitOfWork):
    """Без транзакцій: сховище в пам'яті змінюється лише через save() після всіх перевірок."""

    def transaction(self) -> AbstractContextManager[None]:
        return nullcontext()


class InMemoryOutbox(Outbox):
    """Вихідна черга в пам'яті процесу sales; у ЛР 5 – таблиця в одній базі із замовленнями.

    Доступ захищено блокуванням: події додає обробник запиту, а публікує фоновий потік.
    """

    def __init__(self) -> None:
        self._events: dict[UUID, OrderPaid] = {}
        self._lock = threading.Lock()

    def add(self, event: OrderPaid) -> None:
        with self._lock:
            self._events[event.message_id] = event

    def pending(self) -> list[OrderPaid]:
        with self._lock:
            return list(self._events.values())

    def mark_published(self, message_id: UUID) -> None:
        with self._lock:
            self._events.pop(message_id, None)

"""Сценарій «Резервування місць»: покупець обирає місця на заході."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sales.application.get_hall_layout import HallLayoutCache
from sales.application.unit_of_work import UnitOfWork
from sales.domain.order import Order
from sales.domain.repositories import (
    EventRepository,
    OrderRepository,
    ReservationRepository,
)
from sales.domain.reservation import Reservation
from sales.domain.value_objects import SeatPosition


@dataclass(frozen=True)
class ReserveSeatsCommand:
    """Вхідні дані: захід, покупець і обрані місця (сектор, ряд, номер)."""

    event_id: UUID
    buyer_id: UUID
    seats: tuple[tuple[str, int, int], ...]


@dataclass(frozen=True)
class ReserveSeatsResult:
    """Вихідні дані: замовлення, яке покупець має оплатити до pay_until."""

    order_id: UUID
    total_amount: Decimal
    currency: str
    pay_until: datetime


class ReserveSeats:
    """Резервує місця та створює замовлення із зафіксованими цінами.

    Транзакційна межа – одна одиниця роботи: захід, резервування й замовлення зберігаються
    разом або жодне. Захід завантажується з блокуванням, тож одночасні резервування того
    самого заходу виконуються по черзі й не можуть зайняти одне місце двічі (С-03), а ліміт
    покупця рахується без гонитви (С-06). Усі доменні перевірки – до першого save().
    Після фіксації транзакції кешована схема залу стає недійсною: місця вже не вільні.
    """

    def __init__(
        self,
        events: EventRepository,
        reservations: ReservationRepository,
        orders: OrderRepository,
        clock: Callable[[], datetime],
        unit_of_work: UnitOfWork,
        hall_layout_cache: HallLayoutCache,
    ) -> None:
        self._events = events
        self._reservations = reservations
        self._orders = orders
        self._clock = clock
        self._unit_of_work = unit_of_work
        self._hall_layout_cache = hall_layout_cache

    def execute(self, command: ReserveSeatsCommand) -> ReserveSeatsResult:
        now = self._clock()
        positions = [SeatPosition(*seat) for seat in command.seats]
        with self._unit_of_work.transaction():
            event = self._events.get_for_update(command.event_id)
            held = self._reservations.count_seats_held(command.buyer_id, event.id, now)

            reservation = Reservation.create(event.id, command.buyer_id, positions, now, held)
            event.reserve_seats(positions, now)
            order = Order.for_reservation(reservation, event)

            self._events.save(event)
            self._reservations.save(reservation)
            self._orders.save(order)
        self._hall_layout_cache.invalidate(event.id)

        return ReserveSeatsResult(
            order.id, order.total.amount, order.total.currency, order.payment_deadline
        )
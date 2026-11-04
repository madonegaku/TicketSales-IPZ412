"""Єдина точка складання залежностей сервісу sales (composition root).

Тут – і лише тут – створюються конкретні реалізації інфраструктури
та передаються в сценарії використання. Жоден шар не створює їх самостійно.
"""

from datetime import datetime, timezone

from sales.application.get_hall_layout import GetHallLayout
from sales.application.pay_order import PayOrder
from sales.application.reserve_seats import ReserveSeats
from sales.infrastructure.demo_data import seed_demo_event
from sales.infrastructure.in_memory import (
    InMemoryEventRepository,
    InMemoryOrderRepository,
    InMemoryReservationRepository,
)
from sales.infrastructure.payment import StubPaymentGateway


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Container:
    """Набір готових до використання сценаріїв із підставленими залежностями."""

    def __init__(self) -> None:
        events = InMemoryEventRepository()
        reservations = InMemoryReservationRepository()
        orders = InMemoryOrderRepository()
        seed_demo_event(events)

        self.get_hall_layout = GetHallLayout(events)
        self.reserve_seats = ReserveSeats(events, reservations, orders, utc_now)
        self.pay_order = PayOrder(events, orders, StubPaymentGateway(), utc_now)


container = Container()
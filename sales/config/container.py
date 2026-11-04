"""Єдина точка складання залежностей сервісу sales (composition root).

Тут – і лише тут – створюються конкретні реалізації інфраструктури
та передаються в сценарії використання. Жоден шар не створює їх самостійно.
"""

from datetime import datetime, timezone

import httpx
from django.conf import settings

from sales.application.get_hall_layout import GetHallLayout
from sales.application.pay_order import PayOrder
from sales.application.reserve_seats import ReserveSeats
from sales.infrastructure.demo_data import seed_demo_event
from sales.infrastructure.in_memory import (
    InMemoryEventRepository,
    InMemoryOrderRepository,
    InMemoryOutbox,
    InMemoryReservationRepository,
)
from sales.infrastructure.payments_client import HttpPaymentGateway


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
        self.outbox = InMemoryOutbox()
        payment_gateway = HttpPaymentGateway(
            httpx.Client(base_url=settings.PAYMENTS_URL, timeout=settings.PAYMENTS_TIMEOUT_SECONDS)
        )
        self.pay_order = PayOrder(events, orders, payment_gateway, self.outbox, utc_now)


container = Container()
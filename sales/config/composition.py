"""Складання залежностей сервісу sales (composition root): клас Container.

Тут – і лише тут – створюються конкретні реалізації інфраструктури та передаються в сценарії
використання. Зовнішні залежності (сервіс payments, брокер подій) створюють фабричні методи
(патерн Factory Method): підклас контейнера може підставити інші реалізації – наприклад, у
тесті складання без мережі. Модуль не залежить від Django: налаштування передаються явно,
тож контейнер можна створити в будь-якому процесі; екземпляр для веб-процесу створює
config/container.py.
"""

from datetime import datetime, timezone
from typing import Protocol

import httpx
import redis

from sales.application.get_hall_layout import GetHallLayout
from sales.application.pay_order import PayOrder
from sales.application.publish_pending_events import PublishPendingEvents
from sales.application.reserve_seats import ReserveSeats
from sales.domain.event_publisher import EventPublisher
from sales.domain.payment_gateway import PaymentGateway
from sales.infrastructure.demo_data import seed_demo_event
from sales.infrastructure.in_memory import (
    InMemoryEventRepository,
    InMemoryOrderRepository,
    InMemoryOutbox,
    InMemoryReservationRepository,
)
from sales.infrastructure.outbox_relay import OutboxRelay
from sales.infrastructure.payments_client import HttpPaymentGateway
from sales.infrastructure.redis_publisher import RedisStreamPublisher


class SalesConfig(Protocol):
    """Налаштування, потрібні для складання; їх має django.conf.settings сервісу sales."""

    PAYMENTS_URL: str
    PAYMENTS_TIMEOUT_SECONDS: float
    REDIS_URL: str


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Container:
    """Набір готових до використання сценаріїв із підставленими залежностями."""

    def __init__(self, config: SalesConfig) -> None:
        self._config = config
        events = InMemoryEventRepository()
        reservations = InMemoryReservationRepository()
        orders = InMemoryOrderRepository()
        seed_demo_event(events)

        self.get_hall_layout = GetHallLayout(events)
        self.reserve_seats = ReserveSeats(events, reservations, orders, utc_now)
        self.outbox = InMemoryOutbox()
        self.pay_order = PayOrder(events, orders, self.create_payment_gateway(), self.outbox, utc_now)
        self.outbox_relay = OutboxRelay(PublishPendingEvents(self.outbox, self.create_event_publisher()))

    def create_payment_gateway(self) -> PaymentGateway:
        """Фабричний метод: платіжний шлюз – HTTP-клієнт сервісу payments із тайм-аутом."""
        return HttpPaymentGateway(
            httpx.Client(base_url=self._config.PAYMENTS_URL, timeout=self._config.PAYMENTS_TIMEOUT_SECONDS)
        )

    def create_event_publisher(self) -> EventPublisher:
        """Фабричний метод: публікація подій у Redis Streams."""
        redis_client = redis.Redis.from_url(self._config.REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
        return RedisStreamPublisher(redis_client)

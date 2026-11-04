"""Складання залежностей сервісу sales (composition root): клас Container.

Тут – і лише тут – створюються конкретні реалізації інфраструктури та передаються в сценарії
використання. Зовнішні залежності (сховище, сервіс payments, брокер подій) створюють фабричні
методи (патерн Factory Method): підклас контейнера може підставити інші реалізації – наприклад,
у тесті складання без мережі. Модуль не залежить від Django: налаштування передаються явно,
тож контейнер можна створити в будь-якому процесі; екземпляр для веб-процесу створює
config/container.py.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

import httpx
import redis

from sales.application.get_buyer_orders import GetBuyerOrders
from sales.application.get_hall_layout import GetHallLayout, HallLayoutCache
from sales.application.list_events import ListEvents
from sales.application.pay_order import PayOrder
from sales.application.publish_pending_events import PublishPendingEvents
from sales.application.reserve_seats import ReserveSeats
from sales.application.unit_of_work import UnitOfWork
from sales.domain.event_publisher import EventPublisher
from sales.domain.outbox import Outbox
from sales.domain.payment_gateway import PaymentGateway
from sales.domain.repositories import EventRepository, OrderRepository, ReservationRepository
from sales.infrastructure.demo_data import ensure_demo_event
from sales.infrastructure.hall_layout_cache import NoHallLayoutCache, RedisHallLayoutCache
from sales.infrastructure.in_memory import (
    InMemoryEventRepository,
    InMemoryOrderRepository,
    InMemoryOutbox,
    InMemoryReservationRepository,
    InMemoryUnitOfWork,
)
from sales.infrastructure.outbox_relay import OutboxRelay
from sales.infrastructure.payments_client import HttpPaymentGateway
from sales.infrastructure.postgres.database import Database
from sales.infrastructure.postgres.migrate import migrate_database
from sales.infrastructure.postgres.outbox import PostgresOutbox
from sales.infrastructure.postgres.repositories import (
    PostgresEventRepository,
    PostgresOrderRepository,
    PostgresReservationRepository,
)
from sales.infrastructure.postgres.unit_of_work import PostgresUnitOfWork
from sales.infrastructure.redis_publisher import RedisStreamPublisher


class SalesConfig(Protocol):
    """Налаштування, потрібні для складання; їх має django.conf.settings сервісу sales.

    SALES_DATABASE_URL – рядок підключення до власної бази sales (PostgreSQL); якщо не задано,
    сховище в пам'яті процесу (запуск без Docker, тести складання).
    HALL_LAYOUT_CACHE_TTL – час життя запису кешу схеми залу в секундах; 0 – кеш вимкнено.
    """

    PAYMENTS_URL: str
    PAYMENTS_TIMEOUT_SECONDS: float
    REDIS_URL: str
    SALES_DATABASE_URL: str | None
    HALL_LAYOUT_CACHE_TTL: int


@dataclass(frozen=True)
class Storage:
    """Сховище sales: репозиторії агрегатів, вихідна черга й межа транзакції – з одного джерела."""

    events: EventRepository
    reservations: ReservationRepository
    orders: OrderRepository
    outbox: Outbox
    unit_of_work: UnitOfWork


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Container:
    """Набір готових до використання сценаріїв із підставленими залежностями."""

    def __init__(self, config: SalesConfig) -> None:
        self._config = config
        storage = self.create_storage()
        ensure_demo_event(storage.events)
        cache = self.create_hall_layout_cache()

        self.outbox = storage.outbox
        self.get_hall_layout = GetHallLayout(storage.events, cache)
        self.list_events = ListEvents(storage.events)
        self.get_buyer_orders = GetBuyerOrders(storage.orders, storage.events)
        self.reserve_seats = ReserveSeats(
            storage.events, storage.reservations, storage.orders, utc_now, storage.unit_of_work, cache
        )
        self.pay_order = PayOrder(
            storage.events, storage.orders, self.create_payment_gateway(), storage.outbox, utc_now,
            storage.unit_of_work, cache,
        )
        self.outbox_relay = OutboxRelay(PublishPendingEvents(storage.outbox, self.create_event_publisher()))

    def create_storage(self) -> Storage:
        """Фабричний метод: власна база sales у PostgreSQL (міграції – під час старту) або пам'ять."""
        if not self._config.SALES_DATABASE_URL:
            return Storage(
                InMemoryEventRepository(), InMemoryReservationRepository(), InMemoryOrderRepository(),
                InMemoryOutbox(), InMemoryUnitOfWork(),
            )
        migrate_database(self._config.SALES_DATABASE_URL)
        database = Database(self._config.SALES_DATABASE_URL)
        return Storage(
            PostgresEventRepository(database), PostgresReservationRepository(database),
            PostgresOrderRepository(database), PostgresOutbox(database), PostgresUnitOfWork(database),
        )

    def create_hall_layout_cache(self) -> HallLayoutCache:
        """Фабричний метод: кеш схеми залу в Redis (короткі тайм-аути – збій Redis не гальмує сторінку)."""
        if self._config.HALL_LAYOUT_CACHE_TTL <= 0:
            return NoHallLayoutCache()
        client = redis.Redis.from_url(self._config.REDIS_URL, socket_connect_timeout=0.2, socket_timeout=0.2)
        return RedisHallLayoutCache(client, self._config.HALL_LAYOUT_CACHE_TTL)

    def create_payment_gateway(self) -> PaymentGateway:
        """Фабричний метод: платіжний шлюз – HTTP-клієнт сервісу payments із тайм-аутом."""
        return HttpPaymentGateway(
            httpx.Client(base_url=self._config.PAYMENTS_URL, timeout=self._config.PAYMENTS_TIMEOUT_SECONDS)
        )

    def create_event_publisher(self) -> EventPublisher:
        """Фабричний метод: публікація подій у Redis Streams."""
        redis_client = redis.Redis.from_url(self._config.REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
        return RedisStreamPublisher(redis_client)

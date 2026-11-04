"""Реалізації кешу схеми залу (опис кешу – табл. 5.2 у docs/lab5/data-architecture.md).

RedisHallLayoutCache – робоча: ключ sales:hall-layout:v1:{event_id}, значення – JSON,
час життя – SET … EX. Префікс v1 – версія формату значення: якщо HallLayout зміниться,
нова версія коду читатиме ключі v2 й не зламається на старих записах.
NoHallLayoutCache – «кеш вимкнено» (вимірювання до кешу, запуск без Redis).
InMemoryHallLayoutCache – для тестів сценаріїв: рахує звернення й інвалідизації.
"""

import json
import logging
import threading
import time
from decimal import Decimal
from uuid import UUID

import redis

from sales.application.get_hall_layout import HallLayout, HallLayoutCache, SeatView

logger = logging.getLogger(__name__)

KEY_PREFIX = "sales:hall-layout:v1:"


def key_of(event_id: UUID) -> str:
    return f"{KEY_PREFIX}{event_id}"


def to_json(layout: HallLayout) -> str:
    seats = [
        [s.sector, s.row, s.number, s.category, str(s.price), s.currency, s.is_available] for s in layout.seats
    ]
    return json.dumps({"event_id": str(layout.event_id), "title": layout.title, "seats": seats}, ensure_ascii=False)


def from_json(raw: str | bytes) -> HallLayout:
    data = json.loads(raw)
    return HallLayout(
        UUID(data["event_id"]),
        data["title"],
        tuple(
            SeatView(sector, row, number, category, Decimal(price), currency, is_available)
            for sector, row, number, category, price, currency, is_available in data["seats"]
        ),
    )


class RedisHallLayoutCache(HallLayoutCache):
    """Кеш у Redis. Збій Redis – не збій сценарію: читання стає промахом, запис пропускається.

    Після першого збою кеш вимикається («запобіжник»): запити більше не звертаються до Redis,
    бо кожне звернення до зупиненого Redis чекає DNS і з'єднання – секунди на кожну сторінку
    (виміряно: 7,8 с без запобіжника). Окремий потік раз на retry_interval перевіряє PING; коли
    Redis відповів, потік видаляє всі записи схем залу – поки кеш був вимкнений, інвалідизації не
    доходили, тож будь-який запис міг застаріти, – і лише тоді вмикає кеш знову.
    """

    def __init__(self, client: redis.Redis, ttl_seconds: int, retry_interval: float = 2.0) -> None:
        self._client = client
        self._ttl = ttl_seconds
        self._retry_interval = retry_interval
        self._available = True
        self._lock = threading.Lock()

    @property
    def available(self) -> bool:
        return self._available

    def get(self, event_id: UUID) -> HallLayout | None:
        if not self._available:
            return None
        try:
            raw = self._client.get(key_of(event_id))
        except redis.RedisError as exc:
            self._trip("Кеш схеми залу недоступний – читання з бази", exc)
            return None
        return from_json(raw) if raw is not None else None

    def put(self, layout: HallLayout) -> None:
        if not self._available:
            return
        try:
            self._client.set(key_of(layout.event_id), to_json(layout), ex=self._ttl)
        except redis.RedisError as exc:
            self._trip("Не вдалося записати схему залу в кеш", exc)

    def invalidate(self, event_id: UUID) -> None:
        if not self._available:
            return
        try:
            self._client.delete(key_of(event_id))
        except redis.RedisError as exc:
            self._trip("Не вдалося видалити схему залу з кешу", exc)

    def _trip(self, message: str, exc: Exception) -> None:
        """Вимикає кеш і запускає перевірку відновлення (лише один потік на всі збої)."""
        with self._lock:
            if not self._available:
                return
            self._available = False
        logger.warning("%s: %s. Кеш вимкнено до відновлення Redis.", message, exc)
        threading.Thread(target=self._wait_for_recovery, name="hall-layout-cache-probe", daemon=True).start()

    def _wait_for_recovery(self) -> None:
        while True:
            time.sleep(self._retry_interval)
            try:
                self._client.ping()
                for key in self._client.scan_iter(match=f"{KEY_PREFIX}*"):
                    self._client.delete(key)
            except redis.RedisError:
                continue
            self._available = True
            logger.warning("Redis знову доступний: записи кешу схем залу видалено, кеш увімкнено.")
            return


class NoHallLayoutCache(HallLayoutCache):
    """Кеш вимкнено: завжди промах (вимірювання часу відповіді до кешу)."""

    def get(self, event_id: UUID) -> HallLayout | None:
        return None

    def put(self, layout: HallLayout) -> None:
        pass

    def invalidate(self, event_id: UUID) -> None:
        pass


class InMemoryHallLayoutCache(HallLayoutCache):
    """Кеш у словнику для тестів: рахує влучання, промахи й інвалідизації."""

    def __init__(self) -> None:
        self.entries: dict[UUID, HallLayout] = {}
        self.hits = self.misses = 0
        self.invalidated: list[UUID] = []

    def get(self, event_id: UUID) -> HallLayout | None:
        layout = self.entries.get(event_id)
        if layout is None:
            self.misses += 1
        else:
            self.hits += 1
        return layout

    def put(self, layout: HallLayout) -> None:
        self.entries[layout.event_id] = layout

    def invalidate(self, event_id: UUID) -> None:
        self.entries.pop(event_id, None)
        self.invalidated.append(event_id)

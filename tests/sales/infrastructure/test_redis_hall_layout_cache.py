"""Кеш схеми залу в Redis: ключ, час життя, формат значення й поведінка при недоступному Redis."""

import time
from decimal import Decimal
from uuid import UUID

import redis

from sales.application.get_hall_layout import HallLayout, SeatView
from sales.infrastructure.hall_layout_cache import RedisHallLayoutCache

EVENT_ID = UUID("00000000-0000-0000-0000-000000000018")
LAYOUT = HallLayout(
    EVENT_ID,
    "Концерт симфонічного оркестру",
    (
        SeatView("VIP", 1, 1, "VIP", Decimal("1500.00"), "UAH", True),
        SeatView("Партер", 3, 7, "Партер", Decimal("600.50"), "UAH", False),
    ),
)


class FakeRedis:
    """Мінімальний клієнт Redis: GET, SET з EX, DELETE, PING, SCAN; down=True імітує зупинений Redis."""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.ttl: dict[str, int] = {}
        self.down = False
        self.calls = 0

    def _check(self):
        self.calls += 1
        if self.down:
            raise redis.ConnectionError("Redis недоступний")

    def get(self, key):
        self._check()
        return self.values.get(key)

    def set(self, key, value, ex=None):
        self._check()
        self.values[key], self.ttl[key] = value, ex

    def delete(self, key):
        self._check()
        self.values.pop(key, None)

    def ping(self):
        self._check()
        return True

    def scan_iter(self, match):
        self._check()
        return [key for key in list(self.values) if key.startswith(match.rstrip("*"))]


def wait_until(condition, timeout=2.0):
    deadline = time.monotonic() + timeout
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.01)
    return condition()


def test_layout_is_stored_under_versioned_key_with_ttl_and_read_back_exactly():
    client = FakeRedis()
    cache = RedisHallLayoutCache(client, ttl_seconds=30)

    cache.put(LAYOUT)

    key = "sales:hall-layout:v1:00000000-0000-0000-0000-000000000018"
    assert list(client.values) == [key]
    assert client.ttl[key] == 30
    assert cache.get(EVENT_ID) == LAYOUT


def test_missing_key_is_a_miss_and_invalidate_removes_entry():
    client = FakeRedis()
    cache = RedisHallLayoutCache(client, ttl_seconds=30)
    assert cache.get(EVENT_ID) is None

    cache.put(LAYOUT)
    cache.invalidate(EVENT_ID)

    assert cache.get(EVENT_ID) is None


def test_after_first_failure_requests_stop_touching_redis():
    """Запобіжник: інакше кожна сторінка чекала б DNS і з'єднання зупиненого Redis (7,8 с)."""
    client = FakeRedis()
    client.down = True
    cache = RedisHallLayoutCache(client, ttl_seconds=30, retry_interval=60)

    assert cache.get(EVENT_ID) is None
    calls_after_failure = client.calls
    for _ in range(100):
        assert cache.get(EVENT_ID) is None
        cache.put(LAYOUT)
        cache.invalidate(EVENT_ID)

    assert cache.available is False
    assert client.calls == calls_after_failure


def test_cache_is_cleared_and_enabled_again_after_redis_recovers():
    """Поки кеш був вимкнений, інвалідизації не доходили – після відновлення старі записи видаляються."""
    client = FakeRedis()
    cache = RedisHallLayoutCache(client, ttl_seconds=30, retry_interval=0.01)
    cache.put(LAYOUT)
    client.down = True
    cache.invalidate(EVENT_ID)

    client.down = False

    assert wait_until(lambda: cache.available)
    assert client.values == {}
    assert cache.get(EVENT_ID) is None

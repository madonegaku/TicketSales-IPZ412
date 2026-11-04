"""Тести публікації в Redis Streams: повідомлення відповідає контракту OrderPaid, збої стають доменними."""

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
import redis
import yaml
from jsonschema import Draft7Validator, FormatChecker

from sales.domain.exceptions import EventPublishError
from sales.domain.order_paid import OrderPaid
from sales.domain.value_objects import SeatPosition
from sales.infrastructure.redis_publisher import ORDER_PAID_STREAM, RedisStreamPublisher

CONTRACT_PATH = Path(__file__).resolve().parents[3] / "contracts" / "order-paid.asyncapi.yaml"
CONTRACT = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
NOW = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)


class FakeRedis:
    """Підміна клієнта Redis: запам'ятовує XADD або імітує недоступність."""

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.added: list[tuple[str, dict]] = []

    def xadd(self, stream, fields):
        if self.fail:
            raise redis.ConnectionError("Redis недоступний")
        self.added.append((stream, fields))


def make_event():
    seats = (SeatPosition("Партер", 3, 7), SeatPosition("Партер", 3, 8))
    return OrderPaid(uuid4(), NOW, uuid4(), uuid4(), "Концерт", NOW, seats)


def test_stream_name_matches_contract_channel():
    assert ORDER_PAID_STREAM == CONTRACT["channels"]["orderPaid"]["address"]


def test_published_message_matches_contract():
    client = FakeRedis()

    RedisStreamPublisher(client).publish(make_event())

    stream, fields = client.added[0]
    message = json.loads(fields["payload"])
    schema = {"$ref": "#/components/schemas/OrderPaidV1", "components": CONTRACT["components"]}
    errors = [e.message for e in Draft7Validator(schema, format_checker=FormatChecker()).iter_errors(message)]
    assert stream == ORDER_PAID_STREAM
    assert not errors, f"Повідомлення не відповідає контракту OrderPaidV1: {errors}"


def test_unavailable_redis_raises_publish_error():
    with pytest.raises(EventPublishError):
        RedisStreamPublisher(FakeRedis(fail=True)).publish(make_event())
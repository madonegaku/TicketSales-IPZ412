"""Характеризаційні тести ЛР 4: як споживач OrderPaid користується Redis Streams.

Фіксують поточну поведінку до виділення адаптера: які команди Redis і з якими аргументами
надсилаються, що відбувається з групою, яка вже існує, з повідомленням без поля payload
і з недоступним Redis. Після рефакторингу тести мають проходити без змін.
"""

import json
import logging
from pathlib import Path

import pytest
import redis
import yaml

from tickets.application.issue_tickets import IssueTickets
from tickets.infrastructure.in_memory import InMemoryTicketRepository
from tickets.infrastructure.order_paid_consumer import CONSUMER_GROUP, ORDER_PAID_STREAM, OrderPaidConsumer

CONTRACT_PATH = Path(__file__).resolve().parents[3] / "contracts" / "order-paid.asyncapi.yaml"
EXAMPLE = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))["components"]["messages"]["OrderPaid"][
    "examples"][0]["payload"]


class Stop(Exception):
    """Зупиняє нескінченний цикл run_forever у тесті."""


class RecordingRedis:
    """Підміна клієнта redis-py: записує виклики, відповіді й помилки задаються сценарієм."""

    def __init__(self, reads=(), group_error=None) -> None:
        self.calls: list[tuple] = []
        self.reads = list(reads)
        self.group_error = group_error

    def xgroup_create(self, stream, group, id, mkstream):
        self.calls.append(("xgroup_create", stream, group, id, mkstream))
        if self.group_error is not None:
            error, self.group_error = self.group_error, None
            raise error

    def xreadgroup(self, group, consumer, streams, count, block):
        self.calls.append(("xreadgroup", group, consumer, streams, count, block))
        if not self.reads:
            raise Stop
        result = self.reads.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def xack(self, stream, group, message_id):
        self.calls.append(("xack", stream, group, message_id))


def consumer_for(client):
    return OrderPaidConsumer(client, IssueTickets(InMemoryTicketRepository()), consumer_name="tickets-test")


def test_group_is_created_from_the_beginning_of_the_stream():
    client = RecordingRedis()

    consumer_for(client).ensure_group()

    assert client.calls == [("xgroup_create", ORDER_PAID_STREAM, CONSUMER_GROUP, "0", True)]


def test_existing_group_is_not_an_error():
    client = RecordingRedis(group_error=redis.ResponseError("BUSYGROUP Consumer Group name already exists"))

    consumer_for(client).ensure_group()


def test_other_redis_errors_on_group_creation_are_raised():
    client = RecordingRedis(group_error=redis.ResponseError("WRONGTYPE Operation against a key"))

    with pytest.raises(redis.ResponseError, match="WRONGTYPE"):
        consumer_for(client).ensure_group()


@pytest.mark.parametrize(("start_id", "block_ms"), [(">", 5000), ("0", None)])
def test_batch_is_read_by_the_group_consumer_with_limits(start_id, block_ms):
    client = RecordingRedis(reads=[[]])

    processed = consumer_for(client).process_batch(start_id=start_id, block_ms=block_ms)

    assert processed == 0
    assert client.calls == [("xreadgroup", CONSUMER_GROUP, "tickets-test", {ORDER_PAID_STREAM: start_id}, 10, block_ms)]


def test_empty_response_of_blocking_read_means_no_messages():
    client = RecordingRedis(reads=[None])

    assert consumer_for(client).process_batch() == 0


def test_message_without_payload_is_logged_and_acknowledged(caplog):
    client = RecordingRedis(reads=[[[ORDER_PAID_STREAM, [("5-0", {"other": "x"})]]]])

    with caplog.at_level(logging.ERROR):
        processed = consumer_for(client).process_batch()

    assert processed == 1
    assert client.calls[-1] == ("xack", ORDER_PAID_STREAM, CONSUMER_GROUP, "5-0")
    assert "5-0 відкинуто – не відповідає контракту" in caplog.text


def test_run_forever_reads_own_pending_first_then_new_messages():
    payload = json.dumps(EXAMPLE, ensure_ascii=False)
    client = RecordingRedis(reads=[[[ORDER_PAID_STREAM, [("1-0", {"payload": payload})]]], []])

    with pytest.raises(Stop):
        consumer_for(client).run_forever()

    reads = [call for call in client.calls if call[0] == "xreadgroup"]
    assert [(call[3][ORDER_PAID_STREAM], call[5]) for call in reads] == [("0", None), (">", 5000), (">", 5000)]
    assert ("xack", ORDER_PAID_STREAM, CONSUMER_GROUP, "1-0") in client.calls


def test_run_forever_survives_unavailable_redis_and_starts_over(monkeypatch, caplog):
    sleeps: list[float] = []
    monkeypatch.setattr("time.sleep", sleeps.append)
    client = RecordingRedis(reads=[redis.ConnectionError("Connection refused"), []])

    with caplog.at_level(logging.WARNING), pytest.raises(Stop):
        consumer_for(client).run_forever()

    assert sleeps == [1]
    assert "Redis недоступний – повторна спроба за 1 с." in caplog.text
    assert [call[0] for call in client.calls] == ["xgroup_create", "xreadgroup", "xgroup_create", "xreadgroup", "xreadgroup"]

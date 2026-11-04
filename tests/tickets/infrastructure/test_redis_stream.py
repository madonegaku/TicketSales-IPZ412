"""Тести адаптера RedisConsumerGroup (патерн Adapter, ЛР 4): перетворення інтерфейсу redis-py."""

import pytest
import redis

from tickets.infrastructure.redis_stream import BrokerUnavailableError, RedisConsumerGroup, StreamMessage


class FakeClient:
    def __init__(self, response=None, error=None) -> None:
        self.response = response
        self.error = error
        self.calls: list[tuple] = []

    def _call(self, *call):
        self.calls.append(call)
        if self.error is not None:
            raise self.error
        return self.response

    def xgroup_create(self, stream, group, id, mkstream):
        return self._call("xgroup_create", stream, group, id, mkstream)

    def xreadgroup(self, group, consumer, streams, count, block):
        return self._call("xreadgroup", group, consumer, streams, count, block)

    def xack(self, stream, group, message_id):
        return self._call("xack", stream, group, message_id)


def group_for(client):
    return RedisConsumerGroup(client, "s.v1", "g", "c-1")


def test_nested_redis_response_becomes_flat_list_of_messages():
    client = FakeClient(response=[["s.v1", [("1-0", {"payload": "a"}), ("2-0", {"payload": "b"})]]])

    messages = group_for(client).read(start_id="0", block_ms=None, count=5)

    assert messages == [StreamMessage("1-0", {"payload": "a"}), StreamMessage("2-0", {"payload": "b"})]
    assert client.calls == [("xreadgroup", "g", "c-1", {"s.v1": "0"}, 5, None)]


@pytest.mark.parametrize("response", [None, []])
def test_no_messages_is_empty_list(response):
    assert group_for(FakeClient(response=response)).read() == []


def test_existing_group_is_ignored_and_other_errors_are_not():
    group_for(FakeClient(error=redis.ResponseError("BUSYGROUP Consumer Group name already exists"))).ensure_exists()

    with pytest.raises(redis.ResponseError):
        group_for(FakeClient(error=redis.ResponseError("NOGROUP"))).ensure_exists()


@pytest.mark.parametrize("operation", [
    lambda group: group.ensure_exists(),
    lambda group: group.read(),
    lambda group: group.ack("1-0"),
])
def test_lost_connection_becomes_broker_unavailable(operation):
    with pytest.raises(BrokerUnavailableError):
        operation(group_for(FakeClient(error=redis.ConnectionError("Connection refused"))))


def test_ack_confirms_message_in_own_group():
    client = FakeClient()

    group_for(client).ack("7-0")

    assert client.calls == [("xack", "s.v1", "g", "7-0")]

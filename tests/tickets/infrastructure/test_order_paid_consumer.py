"""Тести споживача OrderPaid: розуміє приклад із контракту, підтверджує лише після обробки, повтори безпечні."""

import json
from pathlib import Path
from uuid import UUID

import pytest
import yaml

from tickets.application.get_order_tickets import GetOrderTickets
from tickets.application.issue_tickets import IssueTickets
from tickets.infrastructure.in_memory import InMemoryTicketRepository
from tickets.infrastructure.order_paid_consumer import ORDER_PAID_STREAM, OrderPaidConsumer, to_command

CONTRACT_PATH = Path(__file__).resolve().parents[3] / "contracts" / "order-paid.asyncapi.yaml"
CONTRACT = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
EXAMPLE = CONTRACT["components"]["messages"]["OrderPaid"]["examples"][0]["payload"]


class FakeRedis:
    """Підміна Redis: віддає заготовлені записи потоку один раз і запам'ятовує XACK."""

    def __init__(self, entries) -> None:
        self.entries = list(entries)
        self.acked: list[str] = []

    def xreadgroup(self, group, consumer, streams, count, block):
        entries, self.entries = self.entries, []
        return [[ORDER_PAID_STREAM, entries]] if entries else []

    def xack(self, stream, group, message_id):
        self.acked.append(message_id)


def test_stream_name_matches_contract_channel():
    assert ORDER_PAID_STREAM == CONTRACT["channels"]["orderPaid"]["address"]


def test_example_message_from_contract_is_understood():
    command = to_command(EXAMPLE)

    assert command.order_id == UUID(EXAMPLE["order_id"])
    assert command.seats == (("Партер", 3, 7), ("Партер", 3, 8))


def test_message_of_unsupported_version_is_rejected():
    with pytest.raises(ValueError):
        to_command({**EXAMPLE, "schema_version": 2})


def test_messages_are_acknowledged_and_duplicates_issue_nothing():
    tickets = InMemoryTicketRepository()
    payload = json.dumps(EXAMPLE, ensure_ascii=False)
    entries = [("1-0", {"payload": payload}), ("2-0", {"payload": payload}), ("3-0", {"payload": "не JSON"})]
    client = FakeRedis(entries)

    processed = OrderPaidConsumer(client, IssueTickets(tickets)).process_batch()

    assert processed == 3
    assert client.acked == ["1-0", "2-0", "3-0"]
    assert len(GetOrderTickets(tickets).execute(UUID(EXAMPLE["order_id"]))) == 2
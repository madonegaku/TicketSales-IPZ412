"""Ідемпотентність обробника OrderPaid на справжньому сховищі SQLite (ЛР 5, крок 6 методички).

Методичка: «перевірити повторним надсиланням тієї самої події» – повтор не змінює результат.
Результат тут – набір квитків замовлення разом із їхніми кодами: після повтору він має бути
тим самим, а не лише такої самої довжини.
"""

import json
import logging
import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import yaml

from tickets.application.issue_tickets import IssueTickets, IssueTicketsCommand
from tickets.infrastructure.order_paid_consumer import ORDER_PAID_STREAM, OrderPaidConsumer
from tickets.infrastructure.sqlite import SqliteTicketRepository

CONTRACT = yaml.safe_load(
    (Path(__file__).resolve().parents[3] / "contracts" / "order-paid.asyncapi.yaml").read_text(encoding="utf-8")
)
EXAMPLE = CONTRACT["components"]["messages"]["OrderPaid"]["examples"][0]["payload"]
ORDER_ID = UUID(EXAMPLE["order_id"])


class FakeRedis:
    """Потік із заготовленими записами: кожне читання віддає наступну порцію."""

    def __init__(self, *batches) -> None:
        self.batches = [list(batch) for batch in batches]
        self.acked: list[str] = []

    def xreadgroup(self, group, consumer, streams, count, block):
        entries = self.batches.pop(0) if self.batches else []
        return [[ORDER_PAID_STREAM, entries]] if entries else []

    def xack(self, stream, group, message_id):
        self.acked.append(message_id)


@pytest.fixture
def tickets(tmp_path):
    return SqliteTicketRepository(tmp_path / "tickets.sqlite3")


def issued_codes(tickets) -> list[str]:
    return [ticket.code for ticket in tickets.list_by_order(ORDER_ID)]


def message(payload: dict) -> dict:
    return {"payload": json.dumps(payload, ensure_ascii=False)}


def test_same_event_sent_again_does_not_change_result(tickets, caplog):
    """Та сама подія (той самий message_id) доставлена вдруге – як після збою споживача до XACK."""
    caplog.set_level(logging.INFO)
    client = FakeRedis([("1-0", message(EXAMPLE))], [("2-0", message(EXAMPLE))])
    consumer = OrderPaidConsumer(client, IssueTickets(tickets))
    consumer.process_batch()
    first = issued_codes(tickets)

    consumer.process_batch()

    assert len(first) == 2
    assert issued_codes(tickets) == first
    assert client.acked == ["1-0", "2-0"]
    assert "повторне повідомлення 2-0" in caplog.text


def test_event_republished_with_new_message_id_is_recognised(tickets):
    """Ключ ідемпотентності – order_id, тож повтор із новим message_id (повторна публікація з outbox) теж нейтральний."""
    client = FakeRedis([("1-0", message(EXAMPLE))], [("2-0", message({**EXAMPLE, "message_id": str(uuid4())}))])
    consumer = OrderPaidConsumer(client, IssueTickets(tickets))
    consumer.process_batch()
    first = issued_codes(tickets)

    consumer.process_batch()

    assert issued_codes(tickets) == first


def test_two_handlers_that_both_passed_the_check_issue_tickets_once(tickets):
    """Дві одночасні обробки: обидві побачили «квитків ще немає». Друга вставка відхиляється базою."""

    class StaleCheckRepository(SqliteTicketRepository):
        def exists_for_order(self, order_id):
            return False

    command = IssueTicketsCommand(ORDER_ID, UUID(EXAMPLE["event_id"]), (("Партер", 3, 7), ("Партер", 3, 8)))
    stale = StaleCheckRepository(tickets._path)

    first = IssueTickets(stale).execute(command)
    second = IssueTickets(stale).execute(command)

    assert (first, second) == (2, 0)
    assert len(issued_codes(tickets)) == 2


def test_database_created_before_lab5_gets_unique_index_and_keeps_tickets(tmp_path):
    path = tmp_path / "tickets.sqlite3"
    IssueTickets(SqliteTicketRepository(path)).execute(
        IssueTicketsCommand(ORDER_ID, UUID(EXAMPLE["event_id"]), (("Партер", 3, 7),))
    )
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("DROP INDEX tickets_one_per_seat_in_order")

    reopened = SqliteTicketRepository(path)

    with closing(sqlite3.connect(path)) as connection:
        indexes = {row[1] for row in connection.execute("PRAGMA index_list(tickets)")}
    assert "tickets_one_per_seat_in_order" in indexes
    assert len(reopened.list_by_order(ORDER_ID)) == 1

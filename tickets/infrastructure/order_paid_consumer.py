"""Споживач події OrderPaid з Redis Streams (контракт contracts/order-paid.asyncapi.yaml).

Читає потік у групі споживачів tickets і підтверджує повідомлення (XACK) лише після видачі квитків.
Не підтверджені до збою повідомлення після перезапуску читаються знову; повтори нейтралізує
ідемпотентний сценарій IssueTickets.
"""

import json
import logging
import time
from uuid import UUID

import redis

from tickets.application.issue_tickets import IssueTickets, IssueTicketsCommand

ORDER_PAID_STREAM = "sales.order-paid.v1"
CONSUMER_GROUP = "tickets"

logger = logging.getLogger(__name__)


def to_command(payload: dict) -> IssueTicketsCommand:
    """Перетворює повідомлення OrderPaid v1 на вхідні дані сценарію; некоректне – ValueError або KeyError."""
    if payload.get("message_type") != "OrderPaid" or payload.get("schema_version") != 1:
        raise ValueError("Непідтримуваний тип або версія повідомлення.")
    seats = tuple((seat["sector"], int(seat["row"]), int(seat["number"])) for seat in payload["seats"])
    return IssueTicketsCommand(UUID(payload["order_id"]), UUID(payload["event_id"]), seats)


class OrderPaidConsumer:
    """Учасник групи споживачів tickets на потоці OrderPaid."""

    def __init__(
        self,
        client: redis.Redis,
        issue_tickets: IssueTickets,
        consumer_name: str = "tickets-1",
        stream: str = ORDER_PAID_STREAM,
    ) -> None:
        self._client = client
        self._issue_tickets = issue_tickets
        self._consumer_name = consumer_name
        self._stream = stream

    def ensure_group(self) -> None:
        """Створює групу споживачів, якщо її ще немає (з першого повідомлення потоку)."""
        try:
            self._client.xgroup_create(self._stream, CONSUMER_GROUP, id="0", mkstream=True)
        except redis.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    def process_batch(self, start_id: str = ">", block_ms: int | None = 5000) -> int:
        """Обробляє порцію повідомлень: «>» – нові, «0» – власні непідтверджені. Повертає їх кількість."""
        response = self._client.xreadgroup(
            CONSUMER_GROUP, self._consumer_name, {self._stream: start_id}, count=10, block=block_ms
        )
        processed = 0
        for _stream, entries in response or []:
            for message_id, fields in entries:
                self._handle(message_id, fields)
                processed += 1
        return processed

    def _handle(self, message_id: str, fields: dict) -> None:
        try:
            command = to_command(json.loads(fields["payload"]))
        except (KeyError, ValueError, TypeError) as exc:
            logger.error("Повідомлення %s відкинуто – не відповідає контракту: %s", message_id, exc)
        else:
            issued = self._issue_tickets.execute(command)
            logger.info("OrderPaid %s: видано квитків – %d", command.order_id, issued)
        self._client.xack(self._stream, CONSUMER_GROUP, message_id)

    def run_forever(self) -> None:
        """Головний цикл процесу: спершу недообробені після збою, далі нові; переживає недоступність Redis."""
        while True:
            try:
                self.ensure_group()
                self.process_batch(start_id="0", block_ms=None)
                while True:
                    self.process_batch()
            except redis.ConnectionError:
                logger.warning("Redis недоступний – повторна спроба за 1 с.")
                time.sleep(1)
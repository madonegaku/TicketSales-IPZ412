"""Споживач події OrderPaid з Redis Streams (контракт contracts/order-paid.asyncapi.yaml).

Читає потік у групі споживачів tickets і підтверджує повідомлення (XACK) лише після видачі квитків.
Не підтверджені до збою повідомлення після перезапуску читаються знову; повтори нейтралізує
ідемпотентний сценарій IssueTickets.
"""

import json
import logging
import time
from typing import TYPE_CHECKING
from uuid import UUID

from tickets.application.issue_tickets import IssueTickets, IssueTicketsCommand
from tickets.infrastructure.redis_stream import BrokerUnavailableError, RedisConsumerGroup, StreamMessage

if TYPE_CHECKING:
    import redis

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
    """Учасник групи споживачів tickets на потоці OrderPaid.

    З Redis працює лише через адаптер RedisConsumerGroup (патерн Adapter): сам споживач
    відповідає за порядок читання, розбір повідомлень за контрактом і підтвердження.
    """

    def __init__(
        self,
        client: "redis.Redis",
        issue_tickets: IssueTickets,
        consumer_name: str = "tickets-1",
        stream: str = ORDER_PAID_STREAM,
    ) -> None:
        self._issue_tickets = issue_tickets
        self._messages = RedisConsumerGroup(client, stream, CONSUMER_GROUP, consumer_name)

    def ensure_group(self) -> None:
        """Створює групу споживачів, якщо її ще немає (з першого повідомлення потоку)."""
        self._messages.ensure_exists()

    def process_batch(self, start_id: str = ">", block_ms: int | None = 5000) -> int:
        """Обробляє порцію повідомлень: «>» – нові, «0» – власні непідтверджені. Повертає їх кількість."""
        messages = self._messages.read(start_id, block_ms)
        for message in messages:
            self._handle(message)
        return len(messages)

    def _handle(self, message: StreamMessage) -> None:
        try:
            command = to_command(json.loads(message.fields["payload"]))
        except (KeyError, ValueError, TypeError) as exc:
            logger.error("Повідомлення %s відкинуто – не відповідає контракту: %s", message.message_id, exc)
        else:
            issued = self._issue_tickets.execute(command)
            logger.info("OrderPaid %s: видано квитків – %d", command.order_id, issued)
        self._messages.ack(message.message_id)

    def run_forever(self) -> None:
        """Головний цикл процесу: спершу недообробені після збою, далі нові; переживає недоступність Redis."""
        while True:
            try:
                self.ensure_group()
                self.process_batch(start_id="0", block_ms=None)
                while True:
                    self.process_batch()
            except BrokerUnavailableError:
                logger.warning("Redis недоступний – повторна спроба за 1 с.")
                time.sleep(1)
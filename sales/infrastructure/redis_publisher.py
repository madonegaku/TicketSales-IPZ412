"""Публікація подій у Redis Streams – реалізація EventPublisher (контракт contracts/order-paid.asyncapi.yaml).

Тіло повідомлення – JSON за схемою OrderPaidV1 у полі payload запису потоку.
"""

import json

import redis

from sales.domain.event_publisher import EventPublisher
from sales.domain.exceptions import EventPublishError
from sales.domain.order_paid import OrderPaid

ORDER_PAID_STREAM = "sales.order-paid.v1"


def to_message(event: OrderPaid) -> dict:
    """Перетворює доменну подію на повідомлення версії 1 за контрактом."""
    return {
        "message_id": str(event.message_id),
        "message_type": "OrderPaid",
        "schema_version": 1,
        "occurred_at": event.occurred_at.isoformat(),
        "order_id": str(event.order_id),
        "event_id": str(event.event_id),
        "event_title": event.event_title,
        "event_starts_at": event.event_starts_at.isoformat(),
        "seats": [{"sector": seat.sector, "row": seat.row, "number": seat.number} for seat in event.seats],
    }


class RedisStreamPublisher(EventPublisher):
    """Додає подію в потік командою XADD; збої Redis перетворює на доменний EventPublishError."""

    def __init__(self, client: redis.Redis, stream: str = ORDER_PAID_STREAM) -> None:
        self._client = client
        self._stream = stream

    def publish(self, event: OrderPaid) -> None:
        payload = json.dumps(to_message(event), ensure_ascii=False)
        try:
            self._client.xadd(self._stream, {"payload": payload})
        except redis.RedisError as exc:
            raise EventPublishError("Брокер подій недоступний – подія лишається у вихідній черзі.") from exc
"""Тест фонового «поштаря»: поки брокер недоступний, події чекають; після відновлення – доставляються."""

import time
from datetime import datetime, timezone
from uuid import uuid4

from sales.application.publish_pending_events import PublishPendingEvents
from sales.domain.event_publisher import EventPublisher
from sales.domain.exceptions import EventPublishError
from sales.domain.order_paid import OrderPaid
from sales.domain.value_objects import SeatPosition
from sales.infrastructure.in_memory import InMemoryOutbox
from sales.infrastructure.outbox_relay import OutboxRelay

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)


class SwitchablePublisher(EventPublisher):
    def __init__(self) -> None:
        self.available = False
        self.published: list[OrderPaid] = []

    def publish(self, event: OrderPaid) -> None:
        if not self.available:
            raise EventPublishError("Брокер недоступний.")
        self.published.append(event)


def wait_until(condition, timeout=2.0):
    deadline = time.monotonic() + timeout
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.01)
    return condition()


def test_events_wait_while_broker_is_down_and_are_delivered_after_recovery():
    outbox, publisher = InMemoryOutbox(), SwitchablePublisher()
    relay = OutboxRelay(PublishPendingEvents(outbox, publisher), interval=0.01)
    relay.start()
    try:
        outbox.add(OrderPaid(uuid4(), NOW, uuid4(), uuid4(), "Концерт", NOW, (SeatPosition("Партер", 1, 1),)))
        time.sleep(0.1)
        assert len(outbox.pending()) == 1

        publisher.available = True

        assert wait_until(lambda: not outbox.pending())
        assert len(publisher.published) == 1
    finally:
        relay.stop()
        relay.join(timeout=1)


class FlakyOutbox(InMemoryOutbox):
    """Черга, сховище якої спершу недоступне (як вимкнена база sales)."""

    def __init__(self) -> None:
        super().__init__()
        self.failures = 3

    def pending(self):
        if self.failures:
            self.failures -= 1
            raise ConnectionError("база sales недоступна")
        return super().pending()


def test_relay_survives_storage_failure_and_keeps_publishing():
    outbox, publisher = FlakyOutbox(), SwitchablePublisher()
    publisher.available = True
    relay = OutboxRelay(PublishPendingEvents(outbox, publisher), interval=0.01)
    relay.start()
    try:
        outbox.add(OrderPaid(uuid4(), NOW, uuid4(), uuid4(), "Концерт", NOW, (SeatPosition("Партер", 1, 1),)))

        assert wait_until(lambda: len(publisher.published) == 1)
        assert relay.is_alive()
    finally:
        relay.stop()
        relay.join(timeout=1)
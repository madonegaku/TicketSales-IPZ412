"""Тести сценарію PublishPendingEvents: гарантія доставки «щонайменше один раз»."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from sales.application.publish_pending_events import PublishPendingEvents
from sales.domain.event_publisher import EventPublisher
from sales.domain.exceptions import EventPublishError
from sales.domain.order_paid import OrderPaid
from sales.domain.value_objects import SeatPosition
from sales.infrastructure.in_memory import InMemoryOutbox

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)


class RecordingPublisher(EventPublisher):
    """Підміна брокера: запам'ятовує опубліковане; fail_after – скільки подій прийняти до збою."""

    def __init__(self, fail_after: int | None = None) -> None:
        self.fail_after = fail_after
        self.published: list[OrderPaid] = []

    def publish(self, event: OrderPaid) -> None:
        if self.fail_after is not None and len(self.published) >= self.fail_after:
            raise EventPublishError("Брокер недоступний.")
        self.published.append(event)


def make_event():
    return OrderPaid(uuid4(), NOW, uuid4(), uuid4(), "Концерт", NOW, (SeatPosition("Партер", 1, 1),))


def test_all_pending_events_are_published_in_order():
    outbox, first, second = InMemoryOutbox(), make_event(), make_event()
    outbox.add(first)
    outbox.add(second)
    publisher = RecordingPublisher()

    assert PublishPendingEvents(outbox, publisher).execute() == 2

    assert publisher.published == [first, second]
    assert outbox.pending() == []


def test_unpublished_events_stay_in_outbox_when_broker_fails():
    outbox, first, second = InMemoryOutbox(), make_event(), make_event()
    outbox.add(first)
    outbox.add(second)

    with pytest.raises(EventPublishError):
        PublishPendingEvents(outbox, RecordingPublisher(fail_after=1)).execute()

    assert outbox.pending() == [second]
"""Сценарій «Опублікувати події з вихідної черги»: доставка OrderPaid брокеру."""

from sales.domain.event_publisher import EventPublisher
from sales.domain.outbox import Outbox


class PublishPendingEvents:
    """Публікує неопубліковані події в порядку додавання.

    Гарантія «щонайменше один раз»: подія викреслюється з черги лише після успішної
    публікації. Якщо брокер недоступний (EventPublishError), решта подій лишається в черзі
    до наступної спроби; повторну доставку нейтралізує ідемпотентний споживач.
    """

    def __init__(self, outbox: Outbox, publisher: EventPublisher) -> None:
        self._outbox = outbox
        self._publisher = publisher

    def execute(self) -> int:
        """Повертає кількість опублікованих подій."""
        published = 0
        for event in self._outbox.pending():
            self._publisher.publish(event)
            self._outbox.mark_published(event.message_id)
            published += 1
        return published
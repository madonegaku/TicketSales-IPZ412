"""Фоновий «поштар»: періодично публікує події з вихідної черги sales у брокер."""

import logging
import threading

from sales.application.publish_pending_events import PublishPendingEvents
from sales.domain.exceptions import EventPublishError

logger = logging.getLogger(__name__)


class OutboxRelay(threading.Thread):
    """Потік-демон: раз на interval секунд викликає PublishPendingEvents.

    Недоступність брокера не зупиняє потік: події чекають у черзі до наступної спроби.
    """

    def __init__(self, publish_pending: PublishPendingEvents, interval: float = 1.0) -> None:
        super().__init__(name="outbox-relay", daemon=True)
        self._publish_pending = publish_pending
        self._interval = interval
        self._stopped = threading.Event()

    def run(self) -> None:
        while not self._stopped.wait(self._interval):
            try:
                self._publish_pending.execute()
            except EventPublishError as exc:
                logger.warning("%s", exc)

    def stop(self) -> None:
        self._stopped.set()
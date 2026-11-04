"""Інтерфейс вихідної черги (outbox): події, які sales має доставити іншим сервісам."""

from abc import ABC, abstractmethod
from uuid import UUID

from sales.domain.order_paid import OrderPaid


class Outbox(ABC):
    """Черга подій на публікацію; подія лишається в ній, доки брокер не підтвердить прийом."""

    @abstractmethod
    def add(self, event: OrderPaid) -> None:
        """Додає подію до черги."""

    @abstractmethod
    def pending(self) -> list[OrderPaid]:
        """Ще не опубліковані події в порядку додавання."""

    @abstractmethod
    def mark_published(self, message_id: UUID) -> None:
        """Позначає подію опублікованою – вона більше не повертається з pending()."""
"""Інтерфейс публікації подій у брокер; реалізація – в інфраструктурному шарі (Redis Streams)."""

from abc import ABC, abstractmethod

from sales.domain.order_paid import OrderPaid


class EventPublisher(ABC):
    """Доставляє доменні події іншим сервісам через брокер повідомлень."""

    @abstractmethod
    def publish(self, event: OrderPaid) -> None:
        """Публікує подію; якщо брокер недоступний – кидає EventPublishError."""
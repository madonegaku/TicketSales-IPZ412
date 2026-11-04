"""Інтерфейси репозиторіїв tickets: колекції агрегатів у термінах предметної області.

Домен лише оголошує, що йому потрібно; реалізації – в інфраструктурному шарі.
"""

from abc import ABC, abstractmethod
from uuid import UUID

from tickets.domain.ticket import Ticket


class TicketRepository(ABC):
    """Колекція квитків."""

    @abstractmethod
    def get_by_code(self, code: str) -> Ticket:
        """Повертає квиток за кодом із QR; якщо його немає – кидає NotFoundError."""

    @abstractmethod
    def save(self, ticket: Ticket) -> None:
        """Додає квиток або оновлює стан наявного (валідація, повернення)."""

    @abstractmethod
    def add_all(self, tickets: list[Ticket]) -> None:
        """Атомарно додає всі квитки одного замовлення: або всі, або жоден.

        Якщо квиток на будь-яке з цих місць цього замовлення вже є – TicketsAlreadyIssuedError
        і нічого не додається (захист від двох одночасних обробок тієї самої події).
        """

    @abstractmethod
    def exists_for_order(self, order_id: UUID) -> bool:
        """Чи видано вже квитки за замовленням – для ідемпотентної обробки OrderPaid."""

    @abstractmethod
    def list_by_order(self, order_id: UUID) -> list[Ticket]:
        """Квитки замовлення в порядку видачі."""
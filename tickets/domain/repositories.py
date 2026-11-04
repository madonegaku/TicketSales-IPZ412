"""Інтерфейси репозиторіїв tickets: колекції агрегатів у термінах предметної області.

Домен лише оголошує, що йому потрібно; реалізації – в інфраструктурному шарі.
"""

from abc import ABC, abstractmethod

from tickets.domain.ticket import Ticket


class TicketRepository(ABC):
    """Колекція квитків."""

    @abstractmethod
    def get_by_code(self, code: str) -> Ticket:
        """Повертає квиток за кодом із QR; якщо його немає – кидає NotFoundError."""

    @abstractmethod
    def save(self, ticket: Ticket) -> None:
        """Додає новий або оновлює наявний квиток."""
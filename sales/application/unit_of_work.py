"""Одиниця роботи (Unit of Work): межа транзакції сценарію використання."""

from abc import ABC, abstractmethod
from contextlib import AbstractContextManager


class UnitOfWork(ABC):
    """Зміни сховища всередині «with unit_of_work.transaction()» фіксуються разом або жодна.

    Інтерфейс – у шарі застосунку, бо межу транзакції визначає сценарій: лише він знає, які
    агрегати змінюються разом. Реалізації – в інфраструктурі: у PostgreSQL це транзакція бази,
    у пам'яті транзакцій немає (атомарність там дає порядок «усі перевірки – до першого save»).
    """

    @abstractmethod
    def transaction(self) -> AbstractContextManager[None]:
        """Контекст транзакції: COMMIT за успіху, ROLLBACK, якщо блок завершився винятком."""

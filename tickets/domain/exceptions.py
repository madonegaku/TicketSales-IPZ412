"""Доменні винятки сервісу tickets."""


class DomainError(Exception):
    """Базовий виняток доменного шару tickets; шар подання показує його повідомлення."""


class InvalidSeatPositionError(DomainError):
    """Порушено інваріант позиції місця."""


class InvalidPaidOrderError(DomainError):
    """Порушено інваріант оплаченого замовлення: немає місць або місця повторюються."""


class TicketAlreadyUsedError(DomainError):
    """Квиток уже використано – повторний вхід заборонено (С-07)."""


class InvalidTicketError(DomainError):
    """Квиток недійсний: повернений, виданий на інший захід або не підлягає поверненню."""


class NotFoundError(DomainError):
    """Об'єкт не знайдено в репозиторії."""
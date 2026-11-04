"""Доменні винятки сервісу payments."""


class DomainError(Exception):
    """Базовий виняток доменного шару payments."""


class InvalidMoneyError(DomainError):
    """Порушено інваріант грошової суми."""


class InvalidPaymentError(DomainError):
    """Порушено інваріант платежу."""


class IdempotencyConflictError(DomainError):
    """Замовлення вже оплачувалося на іншу суму чи в іншій валюті (контракт: 409)."""


class ProviderUnavailableError(DomainError):
    """Платіжний провайдер недоступний – кошти не списано, запит можна повторити (контракт: 503)."""


class NotFoundError(DomainError):
    """Платежу за замовленням немає (контракт: 404)."""
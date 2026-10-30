"""Доменні винятки: порушення правил предметної області."""


class DomainError(Exception):
    """Базовий виняток доменного шару.

    Шар подання перехоплює саме його, щоб показати користувачеві зрозуміле
    повідомлення, не знаючи деталей конкретного правила.
    """


class InvalidMoneyError(DomainError):
    """Порушено інваріант грошової суми."""


class CurrencyMismatchError(DomainError):
    """Спроба виконати дію над сумами в різних валютах."""


class InvalidSeatPositionError(DomainError):
    """Порушено інваріант позиції місця в схемі залу."""


class SeatNotAvailableError(DomainError):
    """Місце не можна зарезервувати: воно вже зарезервоване або продане."""


class InvalidSeatTransitionError(DomainError):
    """Заборонений перехід стану місця."""


class SalesNotStartedError(DomainError):
    """Продаж квитків на захід ще не розпочався."""


class InvalidSeatSelectionError(DomainError):
    """Вибір місць некоректний: місця немає в схемі залу або його обрано двічі."""


class UnknownPriceCategoryError(DomainError):
    """Місце посилається на цінову категорію, якої немає в заході."""
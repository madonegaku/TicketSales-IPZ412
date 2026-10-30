"""Об'єкти-значення доменної моделі."""

from dataclasses import dataclass
from decimal import Decimal

from ticketing.domain.exceptions import CurrencyMismatchError, InvalidMoneyError


@dataclass(frozen=True)
class Money:
    """Грошова сума в певній валюті.

    Інваріанти: сума – скінченне невід'ємне число типу Decimal з точністю
    до копійок; валюта – трилітерний код ISO 4217 (наприклад, UAH).
    """

    amount: Decimal
    currency: str = "UAH"

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal) or not self.amount.is_finite():
            raise InvalidMoneyError("Сума має бути скінченним числом типу Decimal.")
        if self.amount < 0:
            raise InvalidMoneyError("Сума не може бути від'ємною.")
        if self.amount.as_tuple().exponent < -2:
            raise InvalidMoneyError("Сума не може мати більше двох знаків після коми.")
        if len(self.currency) != 3 or not (self.currency.isalpha() and self.currency.isupper()):
            raise InvalidMoneyError("Валюта має бути трилітерним кодом, наприклад UAH.")

    def __add__(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise CurrencyMismatchError("Не можна додавати суми в різних валютах.")
        return Money(self.amount + other.amount, self.currency)
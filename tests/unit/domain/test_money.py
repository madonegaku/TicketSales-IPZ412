"""Тести об'єкта-значення Money: інваріанти, додавання, незмінність."""

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from ticketing.domain.exceptions import CurrencyMismatchError, InvalidMoneyError
from ticketing.domain.value_objects import Money


def test_adding_money_returns_new_value():
    price = Money(Decimal("100.50"))

    total = price + Money(Decimal("49.50"))

    assert total == Money(Decimal("150.00"))
    assert price == Money(Decimal("100.50"))


def test_negative_amount_is_rejected():
    with pytest.raises(InvalidMoneyError):
        Money(Decimal("-1"))


def test_float_amount_is_rejected():
    with pytest.raises(InvalidMoneyError):
        Money(0.1)


def test_more_than_two_decimal_places_is_rejected():
    with pytest.raises(InvalidMoneyError):
        Money(Decimal("10.005"))


def test_adding_different_currencies_is_rejected():
    with pytest.raises(CurrencyMismatchError):
        Money(Decimal("10"), "UAH") + Money(Decimal("10"), "EUR")


def test_money_is_immutable():
    price = Money(Decimal("10"))

    with pytest.raises(FrozenInstanceError):
        price.amount = Decimal("20")
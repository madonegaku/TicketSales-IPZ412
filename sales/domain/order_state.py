"""Стани замовлення (патерн State): які операції оплати дозволені в кожному стані."""

from enum import Enum


class OrderStatus(Enum):
    """Стан замовлення."""

    AWAITING_PAYMENT = "очікує оплати"
    PAYMENT_PENDING = "оплата в обробці"
    PAID = "оплачене"

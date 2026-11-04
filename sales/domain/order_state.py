"""Стани замовлення (патерн State): які операції оплати дозволені в кожному стані.

Order зберігає лише значення OrderStatus (його бачать репозиторії, шаблони й тести), а
рішення «чи дозволена операція і до якого стану вона веде» делегує об'єкту стану.
Кожен стан перевизначає лише дозволені в ньому переходи; заборонені успадковуються від
OrderState з однаковими для всіх станів повідомленнями.
"""

from abc import ABC
from datetime import datetime
from enum import Enum

from sales.domain.exceptions import InvalidOrderError, OrderAlreadyPaidError, ReservationExpiredError


class OrderStatus(Enum):
    """Стан замовлення."""

    AWAITING_PAYMENT = "очікує оплати"
    PAYMENT_PENDING = "оплата в обробці"
    PAID = "оплачене"


class OrderState(ABC):
    """Поведінка замовлення в одному стані; методи повертають наступний стан.

    Об'єкти станів не мають власних даних, тому для кожного стану існує один екземпляр.
    """

    def start_payment(self, payment_deadline: datetime, now: datetime) -> OrderStatus:
        raise InvalidOrderError("Оплата цього замовлення вже розпочата.")

    def resume_payment(self, payment_deadline: datetime, now: datetime) -> OrderStatus:
        return self.start_payment(payment_deadline, now)

    def cancel_payment(self) -> OrderStatus:
        raise InvalidOrderError("Скасувати можна лише розпочату й незавершену оплату.")

    def confirm_payment(self) -> OrderStatus:
        raise InvalidOrderError("Не можна підтвердити оплату, яку не розпочато.")


class AwaitingPayment(OrderState):
    """Очікує оплати: оплату можна розпочати лише до кінця строку резервування (С-04)."""

    def start_payment(self, payment_deadline: datetime, now: datetime) -> OrderStatus:
        if now >= payment_deadline:
            raise ReservationExpiredError("Строк резервування минув – оберіть місця знову.")
        return OrderStatus.PAYMENT_PENDING


class PaymentPending(OrderState):
    """Оплата в обробці: її можна продовжити, підтвердити або скасувати (компенсація)."""

    def resume_payment(self, payment_deadline: datetime, now: datetime) -> OrderStatus:
        return OrderStatus.PAYMENT_PENDING

    def cancel_payment(self) -> OrderStatus:
        return OrderStatus.AWAITING_PAYMENT

    def confirm_payment(self) -> OrderStatus:
        return OrderStatus.PAID


class Paid(OrderState):
    """Оплачене: повторна оплата неможлива (С-05)."""

    def start_payment(self, payment_deadline: datetime, now: datetime) -> OrderStatus:
        raise OrderAlreadyPaidError("Замовлення вже оплачене.")

    def confirm_payment(self) -> OrderStatus:
        raise OrderAlreadyPaidError("Замовлення вже оплачене.")


STATES: dict[OrderStatus, OrderState] = {
    OrderStatus.AWAITING_PAYMENT: AwaitingPayment(),
    OrderStatus.PAYMENT_PENDING: PaymentPending(),
    OrderStatus.PAID: Paid(),
}


def state_of(status: OrderStatus) -> OrderState:
    """Об'єкт стану для значення OrderStatus."""
    return STATES[status]

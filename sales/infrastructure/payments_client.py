"""HTTP-клієнт сервісу payments – реалізація доменного інтерфейсу PaymentGateway (ЛР 3).

Контракт – contracts/payments.openapi.yaml. Кожен виклик обмежено тайм-аутом клієнта: якщо payments
не відповів вчасно, недоступний або тимчасово перевантажений, оплата вважається непідтвердженою
(PaymentUnavailableError) – замовлення лишається в обробці, повтор безпечний (ідемпотентність за order_id).
"""

from uuid import UUID

import httpx

from sales.domain.exceptions import PaymentDeclinedError, PaymentUnavailableError
from sales.domain.payment_gateway import PaymentGateway
from sales.domain.value_objects import Money

UNAVAILABLE_MESSAGE = "Платіжний сервіс не відповів – оплата обробляється, спробуйте ще раз за хвилину."


class HttpPaymentGateway(PaymentGateway):
    """Викликає POST /v1/payments сервісу payments; клієнт httpx створюється в container.py з тайм-аутом."""

    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def charge(self, order_id: UUID, amount: Money) -> None:
        payload = {"order_id": str(order_id), "amount": f"{amount.amount:.2f}", "currency": amount.currency}
        try:
            response = self._client.post("/v1/payments", json=payload)
        except httpx.TransportError as exc:
            raise PaymentUnavailableError(UNAVAILABLE_MESSAGE) from exc

        if response.status_code in (200, 201):
            payment = response.json()
            if payment["status"] == "declined":
                raise PaymentDeclinedError(f"Банк відхилив платіж: {payment['decline_reason']}.")
            return
        if response.status_code == 429 or response.status_code >= 500:
            raise PaymentUnavailableError(UNAVAILABLE_MESSAGE)
        error = response.json()
        raise PaymentDeclinedError(f"Платіжний сервіс відхилив запит: {error['message']}")
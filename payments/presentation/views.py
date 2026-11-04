"""HTTP API сервісу payments за контрактом contracts/payments.openapi.yaml.

View лише перетворює JSON ↔ DTO та доменні винятки ↔ коди відповідей контракту;
правила (ідемпотентність, інваріанти) перевіряє домен.
"""

import json
import re
from decimal import Decimal
from uuid import UUID

from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET, require_POST

from payments.application.create_payment import CreatePayment, CreatePaymentCommand
from payments.application.dto import PaymentResult
from payments.application.get_payment import GetPayment
from payments.domain.exceptions import (
    DomainError,
    IdempotencyConflictError,
    NotFoundError,
    ProviderUnavailableError,
)

AMOUNT_PATTERN = re.compile(r"^[0-9]+(\.[0-9]{1,2})?$")
CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")


def error(status: int, code: str, message: str) -> JsonResponse:
    return JsonResponse({"code": code, "message": message}, status=status)


def payment_json(result: PaymentResult) -> dict:
    return {
        "payment_id": str(result.payment_id),
        "order_id": str(result.order_id),
        "amount": f"{result.amount:.2f}",
        "currency": result.currency,
        "status": result.status,
        "decline_reason": result.decline_reason,
        "created_at": result.created_at.isoformat(),
    }


def parse_command(request: HttpRequest) -> CreatePaymentCommand:
    """Перевіряє формат тіла запиту за схемою PaymentRequest; некоректні дані – ValueError."""
    data = json.loads(request.body)
    amount, currency = data["amount"], data["currency"]
    if not (isinstance(amount, str) and AMOUNT_PATTERN.match(amount)):
        raise ValueError("Некоректна сума.")
    if not (isinstance(currency, str) and CURRENCY_PATTERN.match(currency)):
        raise ValueError("Некоректна валюта.")
    return CreatePaymentCommand(UUID(data["order_id"]), Decimal(amount), currency)


@require_POST
def create(request: HttpRequest, *, create_payment: CreatePayment) -> JsonResponse:
    """POST /v1/payments – списати кошти за замовлення."""
    try:
        command = parse_command(request)
    except (ValueError, KeyError, TypeError):
        return error(400, "invalid_request", "Некоректні дані запиту: перевірте order_id, amount і currency.")
    try:
        result = create_payment.execute(command)
    except IdempotencyConflictError as exc:
        return error(409, "idempotency_conflict", str(exc))
    except ProviderUnavailableError as exc:
        return error(503, "provider_unavailable", str(exc))
    except DomainError as exc:
        return error(400, "invalid_request", str(exc))
    return JsonResponse(payment_json(result), status=200 if result.replayed else 201)


@require_GET
def retrieve(request: HttpRequest, order_id: UUID, *, get_payment: GetPayment) -> JsonResponse:
    """GET /v1/payments/{order_id} – звірка стану оплати."""
    try:
        result = get_payment.execute(order_id)
    except NotFoundError as exc:
        return error(404, "payment_not_found", str(exc))
    return JsonResponse(payment_json(result))
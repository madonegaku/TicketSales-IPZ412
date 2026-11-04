"""JSON API tickets для сервісу web (ADR-006, контракт contracts/tickets.openapi.yaml).

Квитки замовлення: tickets не знає покупця замовлення (у події OrderPaid його немає), тож
власника перевіряє web у sales (GET /api/v1/orders/{id}) перед цим запитом. Валідація на
вході – лише для ролей inspector і admin.
"""

import json
import re
from uuid import UUID

from django.http import HttpRequest, JsonResponse

from tickets.application.get_order_tickets import GetOrderTickets
from tickets.application.validate_ticket import ValidateTicket, ValidateTicketCommand
from tickets.domain.exceptions import DomainError, NotFoundError
from tickets.presentation.auth import Principal, error, read_json


def ok(body: dict) -> JsonResponse:
    return JsonResponse(body, json_dumps_params={"ensure_ascii": False})


def domain_error(exc: DomainError) -> JsonResponse:
    status = 404 if isinstance(exc, NotFoundError) else 409
    code = re.sub(r"(?<!^)(?=[A-Z])", "_", type(exc).__name__.removesuffix("Error")).lower()
    return error(status, code, str(exc))


def order_tickets(request: HttpRequest, order_id: UUID, *, principal: Principal,
                  get_order_tickets: GetOrderTickets) -> JsonResponse:
    """Квитки замовлення; порожній список – подія OrderPaid ще в дорозі («Квитки ще видаються»)."""
    if request.method != "GET":
        return error(405, "method_not_allowed", "Метод не підтримується.")
    tickets = [
        {"code": t.code, "sector": t.sector, "row": t.row, "number": t.number, "status": t.state}
        for t in get_order_tickets.execute(order_id)
    ]
    return ok({"order_id": str(order_id), "tickets": tickets})


def validate(request: HttpRequest, *, principal: Principal, validate_ticket: ValidateTicket) -> JsonResponse:
    """Контролер на вході: пропустити за кодом квитка на свій захід (С-07)."""
    if request.method != "POST":
        return error(405, "method_not_allowed", "Метод не підтримується.")
    try:
        data = read_json(request)
        command = ValidateTicketCommand(str(data["code"]).strip(), UUID(str(data["event_id"])))
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return error(400, "invalid_request", "Очікується {\"code\": \"…\", \"event_id\": \"…\"}.")
    try:
        result = validate_ticket.execute(command)
    except DomainError as exc:
        return domain_error(exc)
    return ok({"admitted": True, "sector": result.sector, "row": result.row, "number": result.number})

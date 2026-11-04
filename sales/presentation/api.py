"""JSON API sales для сервісу web (ADR-006, контракт contracts/sales.openapi.yaml).

Обробники лише перетворюють JSON на команди сценаріїв і результати – на JSON; правила перевіряє
домен. Користувача (principal) визначає обгортка authenticated із токена доступу, тож покупець
завжди діє від власного імені: buyer_id береться з токена, а не з тіла запиту.
"""

import re
from uuid import UUID

from django.http import HttpRequest, JsonResponse

from sales.application.get_buyer_orders import GetBuyerOrders, OrderView
from sales.application.get_hall_layout import GetHallLayout
from sales.application.list_events import ListEvents
from sales.application.pay_order import PayOrder, PayOrderCommand
from sales.application.reserve_seats import ReserveSeats, ReserveSeatsCommand
from sales.domain.exceptions import (
    DomainError,
    InvalidSeatPositionError,
    InvalidSeatSelectionError,
    NotFoundError,
    PaymentDeclinedError,
    PaymentUnavailableError,
)
from sales.presentation.auth import Principal, error, read_json

STATUS_OF = {
    NotFoundError: 404,
    InvalidSeatSelectionError: 400,
    InvalidSeatPositionError: 400,
    PaymentDeclinedError: 402,
    PaymentUnavailableError: 503,
}


def money(amount) -> str:
    return f"{amount:.2f}"


def ok(body: dict, status: int = 200) -> JsonResponse:
    return JsonResponse(body, status=status, json_dumps_params={"ensure_ascii": False})


def domain_error(exc: DomainError) -> JsonResponse:
    """Доменний виняток → HTTP: код помилки – назва винятку в snake_case без «Error» (seat_not_available)."""
    status = next((code for kind, code in STATUS_OF.items() if isinstance(exc, kind)), 409)
    code = re.sub(r"(?<!^)(?=[A-Z])", "_", type(exc).__name__.removesuffix("Error")).lower()
    return error(status, code, str(exc))


def method_not_allowed() -> JsonResponse:
    return error(405, "method_not_allowed", "Метод не підтримується.")


def order_json(view: OrderView) -> dict:
    return {
        "order_id": str(view.order_id),
        "event_id": str(view.event_id),
        "event_title": view.event_title,
        "status": view.status,
        "total_amount": money(view.total_amount),
        "currency": view.currency,
        "payment_deadline": view.payment_deadline.isoformat(),
        "seats": [{"sector": s.sector, "row": s.row, "number": s.number, "price": money(s.price)} for s in view.seats],
    }


def list_events(request: HttpRequest, *, principal: Principal, list_events: ListEvents) -> JsonResponse:
    if request.method != "GET":
        return method_not_allowed()
    events = [
        {
            "event_id": str(e.event_id), "title": e.title, "sales_start": e.sales_start.isoformat(),
            "starts_at": e.starts_at.isoformat(), "seats_total": e.seats_total, "seats_available": e.seats_available,
            "price_from": money(e.price_from), "currency": e.currency,
        }
        for e in list_events.execute()
    ]
    return ok({"events": events})


def hall(request: HttpRequest, event_id: UUID, *, principal: Principal, get_hall_layout: GetHallLayout) -> JsonResponse:
    if request.method != "GET":
        return method_not_allowed()
    try:
        layout = get_hall_layout.execute(event_id)
    except DomainError as exc:
        return domain_error(exc)
    seats = [
        {"sector": s.sector, "row": s.row, "number": s.number, "category": s.category, "price": money(s.price),
         "currency": s.currency, "is_available": s.is_available}
        for s in layout.seats
    ]
    return ok({"event_id": str(layout.event_id), "title": layout.title, "seats": seats})


def reserve(request: HttpRequest, event_id: UUID, *, principal: Principal, reserve_seats: ReserveSeats) -> JsonResponse:
    if request.method != "POST":
        return method_not_allowed()
    try:
        seats = tuple((s["sector"], int(s["row"]), int(s["number"])) for s in read_json(request)["seats"])
    except (ValueError, KeyError, TypeError):
        return error(400, "invalid_request", "Очікується {\"seats\": [{\"sector\", \"row\", \"number\"}, …]}.")
    try:
        result = reserve_seats.execute(ReserveSeatsCommand(event_id, principal.subject_id, seats))
    except DomainError as exc:
        return domain_error(exc)
    return ok({
        "order_id": str(result.order_id), "total_amount": money(result.total_amount), "currency": result.currency,
        "pay_until": result.pay_until.isoformat(),
    }, status=201)


def pay(request: HttpRequest, order_id: UUID, *, principal: Principal, pay_order: PayOrder) -> JsonResponse:
    if request.method != "POST":
        return method_not_allowed()
    try:
        result = pay_order.execute(PayOrderCommand(order_id, buyer_id=principal.subject_id))
    except DomainError as exc:
        return domain_error(exc)
    return ok({"order_id": str(result.order_id), "status": "PAID"})


def my_orders(request: HttpRequest, *, principal: Principal, get_buyer_orders: GetBuyerOrders) -> JsonResponse:
    if request.method != "GET":
        return method_not_allowed()
    return ok({"orders": [order_json(view) for view in get_buyer_orders.execute(principal.subject_id)]})


def my_order(request: HttpRequest, order_id: UUID, *, principal: Principal,
             get_buyer_orders: GetBuyerOrders) -> JsonResponse:
    if request.method != "GET":
        return method_not_allowed()
    try:
        return ok(order_json(get_buyer_orders.one(principal.subject_id, order_id)))
    except DomainError as exc:
        return domain_error(exc)

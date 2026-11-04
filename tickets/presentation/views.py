"""Обробники HTTP-запитів сервісу tickets: перетворюють дані форм на DTO і викликають сценарії.

Бізнес-умов тут немає: правила перевіряє домен, а view лише показує
користувачеві повідомлення доменного винятку.
"""

from uuid import UUID

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from tickets.application.validate_ticket import ValidateTicket, ValidateTicketCommand
from tickets.domain.exceptions import DomainError


def validate(
    request: HttpRequest,
    *,
    validate_ticket: ValidateTicket,
    default_event_id: UUID,
) -> HttpResponse:
    """Сторінка контролера: перевіряє код квитка на вході до заходу."""
    context = {"event_id": request.POST.get("event_id", default_event_id)}
    if request.method == "POST":
        try:
            command = ValidateTicketCommand(
                request.POST["code"].strip(), UUID(request.POST["event_id"])
            )
            context["seat"] = validate_ticket.execute(command)
        except (KeyError, ValueError):
            context["error"] = "Некоректні дані форми."
        except DomainError as exc:
            context["error"] = str(exc)
    return render(request, "presentation/validate.html", context)
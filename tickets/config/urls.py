"""Маршрути URL сервісу tickets. View отримують сценарії з контейнера – це частина точки складання.

Сторінки Django (ЛР 3–5) – для браузера; JSON API /api/v1/… – лише для сервісу web (ADR-006):
кожен виклик перевіряє токен доступу, а шлюз закриває /api/ ззовні.
"""

from functools import partial
from uuid import UUID

from django.conf import settings
from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from tickets.config.container import container
from tickets.presentation import api, views
from tickets.presentation.auth import authenticated


def api_view(view, *roles, **use_cases):
    """JSON API: токен доступу замість cookie, тож CSRF-захист форм Django тут не потрібен."""
    return csrf_exempt(authenticated(partial(view, **use_cases), secret=settings.AUTH_TOKEN_SECRET, roles=roles))


urlpatterns = [
    path(
        "validate/",
        partial(
            views.validate,
            validate_ticket=container.validate_ticket,
            default_event_id=UUID(settings.INSPECTOR_EVENT_ID),
        ),
        name="validate",
    ),
    path(
        "tickets/orders/<uuid:order_id>/",
        partial(views.order_tickets, get_order_tickets=container.get_order_tickets),
        name="order-tickets",
    ),
    path("api/v1/orders/<uuid:order_id>/tickets",
         api_view(api.order_tickets, "buyer", "admin", get_order_tickets=container.get_order_tickets)),
    path("api/v1/validations", api_view(api.validate, "inspector", "admin", validate_ticket=container.validate_ticket)),
]

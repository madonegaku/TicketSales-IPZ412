"""Маршрути URL сервісу sales. View отримують сценарії з контейнера – це частина точки складання.

Сторінки Django (ЛР 2–5) – для браузера; JSON API /api/v1/… – лише для сервісу web (ADR-006):
кожен виклик перевіряє токен доступу, а шлюз закриває /api/ ззовні.
"""

from functools import partial

from django.conf import settings
from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import RedirectView

from sales.config.container import container
from sales.infrastructure.demo_data import DEMO_EVENT_ID
from sales.presentation import api, views
from sales.presentation.auth import authenticated


def api_view(view, *roles, **use_cases):
    """JSON API: токен доступу замість cookie, тож CSRF-захист форм Django тут не потрібен."""
    return csrf_exempt(authenticated(partial(view, **use_cases), secret=settings.AUTH_TOKEN_SECRET, roles=roles))


urlpatterns = [
    path("", RedirectView.as_view(url=f"/events/{DEMO_EVENT_ID}/")),
    path(
        "events/<uuid:event_id>/",
        partial(
            views.hall,
            get_hall_layout=container.get_hall_layout,
            reserve_seats=container.reserve_seats,
        ),
        name="hall",
    ),
    path(
        "orders/<uuid:order_id>/pay/",
        partial(views.pay, pay_order=container.pay_order),
        name="pay",
    ),
    path("api/v1/events",
         api_view(api.events, list_events=container.list_events, create_event=container.create_event)),
    path("api/v1/organizer/events",
         api_view(api.organizer_events, "organizer", "admin", get_organizer_events=container.get_organizer_events)),
    path("api/v1/events/<uuid:event_id>", api_view(api.hall, get_hall_layout=container.get_hall_layout)),
    path("api/v1/events/<uuid:event_id>/reservations",
         api_view(api.reserve, "buyer", reserve_seats=container.reserve_seats)),
    path("api/v1/orders", api_view(api.my_orders, "buyer", get_buyer_orders=container.get_buyer_orders)),
    path("api/v1/orders/<uuid:order_id>",
         api_view(api.my_order, "buyer", get_buyer_orders=container.get_buyer_orders)),
    path("api/v1/orders/<uuid:order_id>/payment", api_view(api.pay, "buyer", pay_order=container.pay_order)),
]

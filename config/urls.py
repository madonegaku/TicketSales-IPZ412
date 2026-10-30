"""Маршрути URL. Тут view отримують сценарії з контейнера – це частина точки складання."""

from functools import partial

from django.urls import path
from django.views.generic import RedirectView

from config.container import container
from ticketing.infrastructure.demo_data import DEMO_EVENT_ID
from ticketing.presentation import views

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
]
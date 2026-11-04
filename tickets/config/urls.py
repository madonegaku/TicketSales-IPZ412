"""Маршрути URL сервісу tickets. View отримують сценарії з контейнера – це частина точки складання."""

from functools import partial
from uuid import UUID

from django.conf import settings
from django.urls import path

from tickets.config.container import container
from tickets.presentation import views

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
]
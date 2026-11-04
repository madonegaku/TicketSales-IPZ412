"""Маршрути HTTP API сервісу payments; версія v1 – у шляху, як у контракті."""

from functools import partial

from django.urls import path

from payments.config.container import container
from payments.presentation import views

urlpatterns = [
    path("v1/payments", partial(views.create, create_payment=container.create_payment), name="create-payment"),
    path(
        "v1/payments/<uuid:order_id>",
        partial(views.retrieve, get_payment=container.get_payment),
        name="get-payment",
    ),
]
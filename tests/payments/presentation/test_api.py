"""Тести HTTP API payments: коди відповідей і тіла відповідають контракту contracts/payments.openapi.yaml."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import django
import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "payments.config.settings")
django.setup()

from django.test import RequestFactory  # noqa: E402

from payments.application.create_payment import CreatePayment  # noqa: E402
from payments.application.get_payment import GetPayment  # noqa: E402
from payments.infrastructure.in_memory import InMemoryPaymentRepository  # noqa: E402
from payments.infrastructure.provider import StubPaymentProvider  # noqa: E402
from payments.presentation import views  # noqa: E402

CONTRACT_PATH = Path(__file__).resolve().parents[3] / "contracts" / "payments.openapi.yaml"
CONTRACT = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
NOW = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)
factory = RequestFactory()


def assert_matches_contract(response, method, path, schema_name):
    """Код відповіді описаний у контракті для операції, а тіло відповідає схемі контракту."""
    assert str(response.status_code) in CONTRACT["paths"][path][method]["responses"]
    schema = {"$ref": f"#/components/schemas/{schema_name}", "components": CONTRACT["components"]}
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = [error.message for error in validator.iter_errors(json.loads(response.content))]
    assert not errors, f"Відповідь не відповідає схемі {schema_name}: {errors}"


@pytest.fixture
def payments():
    return InMemoryPaymentRepository()


def post(payments, body, provider=None):
    create_payment = CreatePayment(payments, provider or StubPaymentProvider(), lambda: NOW)
    request = factory.post("/v1/payments", data=json.dumps(body), content_type="application/json")
    return views.create(request, create_payment=create_payment)


def body(order_id, amount="1200.00"):
    return {"order_id": str(order_id), "amount": amount, "currency": "UAH"}


def test_new_payment_is_created(payments):
    response = post(payments, body(uuid4()))

    assert response.status_code == 201
    assert_matches_contract(response, "post", "/payments", "Payment")
    assert json.loads(response.content)["status"] == "succeeded"


def test_repeated_request_returns_same_payment(payments):
    order_id = uuid4()
    first = json.loads(post(payments, body(order_id)).content)

    response = post(payments, body(order_id))

    assert response.status_code == 200
    assert_matches_contract(response, "post", "/payments", "Payment")
    assert json.loads(response.content)["payment_id"] == first["payment_id"]


def test_declined_payment_has_reason(payments):
    response = post(payments, body(uuid4()), StubPaymentProvider(decline_reason="Недостатньо коштів"))

    assert response.status_code == 201
    assert_matches_contract(response, "post", "/payments", "Payment")
    assert json.loads(response.content)["decline_reason"] == "Недостатньо коштів"


def test_other_amount_for_same_order_is_conflict(payments):
    order_id = uuid4()
    post(payments, body(order_id))

    response = post(payments, body(order_id, "1500.00"))

    assert response.status_code == 409
    assert_matches_contract(response, "post", "/payments", "Error")


@pytest.mark.parametrize("bad", [{"amount": "12.345"}, {"currency": "uah"}, {"order_id": "not-a-uuid"}])
def test_invalid_request_is_rejected(payments, bad):
    response = post(payments, {**body(uuid4()), **bad})

    assert response.status_code == 400
    assert_matches_contract(response, "post", "/payments", "Error")


def test_unavailable_provider_gives_503(payments):
    response = post(payments, body(uuid4()), StubPaymentProvider(unavailable=True))

    assert response.status_code == 503
    assert_matches_contract(response, "post", "/payments", "Error")


def test_get_existing_and_missing_payment(payments):
    order_id = uuid4()
    post(payments, body(order_id))
    get_payment = GetPayment(payments)

    found = views.retrieve(factory.get(f"/v1/payments/{order_id}"), order_id, get_payment=get_payment)
    missing = views.retrieve(factory.get("/v1/payments/x"), uuid4(), get_payment=get_payment)

    assert found.status_code == 200
    assert_matches_contract(found, "get", "/payments/{order_id}", "Payment")
    assert missing.status_code == 404
    assert_matches_contract(missing, "get", "/payments/{order_id}", "Error")
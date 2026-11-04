"""Тести HTTP-клієнта payments: запит відповідає контракту, відповіді й збої стають доменними винятками."""

import http.server
import json
import threading
import time
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker

from sales.domain.exceptions import PaymentDeclinedError, PaymentUnavailableError
from sales.domain.value_objects import Money
from sales.infrastructure.payments_client import HttpPaymentGateway

CONTRACT_PATH = Path(__file__).resolve().parents[3] / "contracts" / "payments.openapi.yaml"
CONTRACT = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
ORDER_ID = uuid4()
AMOUNT = Money(Decimal("1200"))


def payment_body(status="succeeded", decline_reason=None):
    return {
        "payment_id": str(uuid4()),
        "order_id": str(ORDER_ID),
        "amount": "1200.00",
        "currency": "UAH",
        "status": status,
        "decline_reason": decline_reason,
        "created_at": "2026-11-04T12:00:00+00:00",
    }


def gateway(handler):
    """Клієнт з підміненою мережею: на кожен запит відповідає функція handler."""
    transport = httpx.MockTransport(handler)
    return HttpPaymentGateway(httpx.Client(base_url="http://payments:8000", transport=transport, timeout=2.0))


def test_request_matches_contract():
    sent = []

    def handler(request):
        sent.append(request)
        return httpx.Response(201, json=payment_body())

    gateway(handler).charge(ORDER_ID, AMOUNT)

    request, body = sent[0], json.loads(sent[0].content)
    schema = {"$ref": "#/components/schemas/PaymentRequest", "components": CONTRACT["components"]}
    errors = [e.message for e in Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(body)]
    assert (request.method, request.url.path) == ("POST", "/v1/payments")
    assert not errors, f"Запит не відповідає схемі PaymentRequest: {errors}"
    assert body["amount"] == "1200.00"


def test_replayed_payment_is_success():
    gateway(lambda request: httpx.Response(200, json=payment_body())).charge(ORDER_ID, AMOUNT)


def test_declined_payment_raises_declined():
    response = httpx.Response(201, json=payment_body("declined", "Недостатньо коштів"))

    with pytest.raises(PaymentDeclinedError, match="Недостатньо коштів"):
        gateway(lambda request: response).charge(ORDER_ID, AMOUNT)


@pytest.mark.parametrize("error", [httpx.ReadTimeout("тайм-аут"), httpx.ConnectError("сервіс недоступний")])
def test_network_failure_means_payment_unavailable(error):
    def handler(request):
        raise error

    with pytest.raises(PaymentUnavailableError):
        gateway(handler).charge(ORDER_ID, AMOUNT)


@pytest.mark.parametrize("status_code", [429, 503])
def test_overloaded_or_unavailable_service_means_payment_unavailable(status_code):
    response = httpx.Response(status_code, json={"code": "provider_unavailable", "message": "Спробуйте пізніше"})

    with pytest.raises(PaymentUnavailableError):
        gateway(lambda request: response).charge(ORDER_ID, AMOUNT)


def test_conflict_is_reported_as_declined():
    response = httpx.Response(409, json={"code": "idempotency_conflict", "message": "Інша сума"})

    with pytest.raises(PaymentDeclinedError, match="Інша сума"):
        gateway(lambda request: response).charge(ORDER_ID, AMOUNT)


def test_real_timeout_with_slow_service():
    """Справжній тайм-аут: локальний сервер відповідає за 1,5 с, клієнт чекає лише 0,5 с."""

    class SlowHandler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            time.sleep(1.5)
            self.send_response(201)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), SlowHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    client = httpx.Client(base_url=f"http://127.0.0.1:{server.server_port}", timeout=0.5)
    try:
        started = time.monotonic()
        with pytest.raises(PaymentUnavailableError):
            HttpPaymentGateway(client).charge(ORDER_ID, AMOUNT)
        assert time.monotonic() - started < 1.4
    finally:
        server.shutdown()
        server.server_close()
"""JSON API tickets для web: квитки замовлення й валідація на вході відповідають contracts/tickets.openapi.yaml."""

import json
from datetime import datetime, timedelta, timezone
from functools import partial
from pathlib import Path
from uuid import uuid4

import jwt
import pytest
import yaml
from django.test import RequestFactory
from jsonschema import Draft202012Validator, FormatChecker

from tickets.application.get_order_tickets import GetOrderTickets
from tickets.application.issue_tickets import IssueTickets, IssueTicketsCommand
from tickets.application.validate_ticket import ValidateTicket
from tickets.infrastructure.in_memory import InMemoryTicketRepository
from tickets.presentation import api
from tickets.presentation.auth import authenticated

CONTRACT = yaml.safe_load(
    (Path(__file__).resolve().parents[3] / "contracts" / "tickets.openapi.yaml").read_text(encoding="utf-8")
)
SECRET = "test-secret-for-tkts-api--tokens-32b"
EVENT_ID, ORDER_ID = uuid4(), uuid4()
factory = RequestFactory()


def token(*roles: str) -> str:
    claims = {"sub": str(uuid4()), "roles": list(roles), "iss": "web", "aud": "ticketsales",
              "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
    return "Bearer " + jwt.encode(claims, SECRET, algorithm="HS256")


def assert_matches_contract(response, method, path):
    operation = CONTRACT["paths"][path][method]
    status = str(response.status_code)
    assert status in operation["responses"], f"{status} не описаний для {method.upper()} {path}"
    described = operation["responses"][status]
    if "$ref" in described:
        described = CONTRACT["components"]["responses"][described["$ref"].rsplit("/", 1)[1]]
    schema = {**described["content"]["application/json"]["schema"], "components": CONTRACT["components"]}
    errors = [e.message for e in Draft202012Validator(schema, format_checker=FormatChecker())
              .iter_errors(json.loads(response.content))]
    assert not errors, f"Відповідь не відповідає контракту: {errors}"


@pytest.fixture
def tickets():
    repository = InMemoryTicketRepository()
    IssueTickets(repository).execute(IssueTicketsCommand(ORDER_ID, EVENT_ID, (("Партер", 3, 7), ("Партер", 3, 8))))
    return repository


def get_tickets(tickets, order_id, *roles):
    view = authenticated(partial(api.order_tickets, get_order_tickets=GetOrderTickets(tickets)), secret=SECRET,
                         roles=("buyer", "admin"))
    return view(factory.get("/", HTTP_AUTHORIZATION=token(*roles)), order_id=order_id)


def validate(tickets, body, *roles):
    view = authenticated(partial(api.validate, validate_ticket=ValidateTicket(tickets)), secret=SECRET,
                         roles=("inspector", "admin"))
    request = factory.post("/", data=json.dumps(body), content_type="application/json",
                           HTTP_AUTHORIZATION=token(*roles))
    return view(request)


def test_order_tickets_match_contract(tickets):
    response = get_tickets(tickets, ORDER_ID, "buyer")

    assert_matches_contract(response, "get", "/orders/{order_id}/tickets")
    body = json.loads(response.content)
    assert [(t["sector"], t["row"], t["number"], t["status"]) for t in body["tickets"]] == [
        ("Партер", 3, 7, "VALID"), ("Партер", 3, 8, "VALID")]


def test_tickets_not_yet_issued_are_an_empty_list(tickets):
    response = get_tickets(tickets, uuid4(), "buyer")

    assert_matches_contract(response, "get", "/orders/{order_id}/tickets")
    assert json.loads(response.content)["tickets"] == []


def test_inspector_admits_once_then_rejects_reused_code(tickets):
    code = tickets.list_by_order(ORDER_ID)[0].code

    first = validate(tickets, {"code": code, "event_id": str(EVENT_ID)}, "inspector")
    again = validate(tickets, {"code": code, "event_id": str(EVENT_ID)}, "inspector")

    for response in (first, again):
        assert_matches_contract(response, "post", "/validations")
    assert json.loads(first.content) == {"admitted": True, "sector": "Партер", "row": 3, "number": 7}
    assert (again.status_code, json.loads(again.content)["code"]) == (409, "ticket_already_used")
    assert get_tickets(tickets, ORDER_ID, "buyer").content.count(b'"USED"') == 1


@pytest.mark.parametrize(
    ("body_of", "status", "code"),
    [
        (lambda code: {"code": code, "event_id": str(uuid4())}, 409, "invalid_ticket"),
        (lambda code: {"code": "немає-такого", "event_id": str(EVENT_ID)}, 404, "not_found"),
        (lambda code: {"code": code}, 400, "invalid_request"),
        (lambda code: {"code": code, "event_id": "не-uuid"}, 400, "invalid_request"),
    ],
    ids=["other-event", "unknown-code", "no-event", "bad-event-id"],
)
def test_entry_is_refused(tickets, body_of, status, code):
    response = validate(tickets, body_of(tickets.list_by_order(ORDER_ID)[0].code), "inspector")

    assert_matches_contract(response, "post", "/validations")
    assert (response.status_code, json.loads(response.content)["code"]) == (status, code)


def test_only_inspectors_validate_and_inspectors_do_not_read_orders(tickets):
    code = tickets.list_by_order(ORDER_ID)[0].code

    by_buyer = validate(tickets, {"code": code, "event_id": str(EVENT_ID)}, "buyer")
    by_inspector = get_tickets(tickets, ORDER_ID, "inspector")

    assert (by_buyer.status_code, by_inspector.status_code) == (403, 403)
    assert tickets.get_by_code(code).status.name == "VALID", "відмова не змінила квиток"

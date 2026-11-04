"""JSON API sales для web: коди й тіла відповідей відповідають contracts/sales.openapi.yaml, покупець – з токена."""

import json
from datetime import datetime, timedelta, timezone
from functools import partial
from pathlib import Path
from uuid import UUID, uuid4

import jwt
import pytest
import yaml
from django.test import RequestFactory
from jsonschema import Draft202012Validator, FormatChecker

from sales.application.create_event import CreateEvent
from sales.application.get_buyer_orders import GetBuyerOrders
from sales.application.get_organizer_events import GetOrganizerEvents
from sales.application.get_hall_layout import GetHallLayout
from sales.application.list_events import ListEvents
from sales.application.pay_order import PayOrder
from sales.application.reserve_seats import ReserveSeats
from sales.infrastructure.demo_data import DEMO_EVENT_ID, seed_demo_event
from sales.infrastructure.hall_layout_cache import NoHallLayoutCache
from sales.infrastructure.in_memory import (
    InMemoryEventRepository,
    InMemoryOrderRepository,
    InMemoryOutbox,
    InMemoryReservationRepository,
    InMemoryUnitOfWork,
)
from sales.infrastructure.payment import StubPaymentGateway
from sales.presentation import api
from sales.presentation.auth import authenticated

CONTRACT = yaml.safe_load(
    (Path(__file__).resolve().parents[3] / "contracts" / "sales.openapi.yaml").read_text(encoding="utf-8")
)
SECRET = "test-secret-for-sales-api-tokens-32b"
NOW = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)
factory = RequestFactory()


def token(subject: UUID, *roles: str) -> str:
    claims = {"sub": str(subject), "roles": list(roles or ("buyer",)), "iss": "web", "aud": "ticketsales",
              "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
    return "Bearer " + jwt.encode(claims, SECRET, algorithm="HS256")


def assert_matches_contract(response, method, path, schema=None):
    """Код відповіді описаний у контракті для операції, а тіло відповідає схемі відповіді контракту."""
    operation = CONTRACT["paths"][path][method]
    status = str(response.status_code)
    assert status in operation["responses"], f"{status} не описаний для {method.upper()} {path}"
    described = operation["responses"][status]
    if "$ref" in described:
        described = CONTRACT["components"]["responses"][described["$ref"].rsplit("/", 1)[1]]
    schema = schema or described["content"]["application/json"]["schema"]
    validator = Draft202012Validator({**schema, "components": CONTRACT["components"]}, format_checker=FormatChecker())
    errors = [e.message for e in validator.iter_errors(json.loads(response.content))]
    assert not errors, f"Відповідь не відповідає контракту: {errors}"


class System:
    def __init__(self, gateway=None) -> None:
        events, orders = InMemoryEventRepository(), InMemoryOrderRepository()
        seed_demo_event(events)
        cache, unit_of_work = NoHallLayoutCache(), InMemoryUnitOfWork()
        self.gateway = gateway or StubPaymentGateway()
        clock = lambda: NOW  # noqa: E731
        reserve_seats = ReserveSeats(events, InMemoryReservationRepository(), orders, clock, unit_of_work, cache)
        pay_order = PayOrder(events, orders, self.gateway, InMemoryOutbox(), clock, unit_of_work, cache)
        get_orders = GetBuyerOrders(orders, events)
        wrap = lambda view, *roles, **deps: authenticated(partial(view, **deps), secret=SECRET, roles=roles)  # noqa: E731
        self.events = wrap(api.events, list_events=ListEvents(events),
                           create_event=CreateEvent(events, unit_of_work))
        self.list_events = self.events
        self.organizer_events = wrap(api.organizer_events, "organizer", "admin",
                                     get_organizer_events=GetOrganizerEvents(events, orders))
        self.hall = wrap(api.hall, get_hall_layout=GetHallLayout(events, cache))
        self.reserve = wrap(api.reserve, "buyer", reserve_seats=reserve_seats)
        self.pay = wrap(api.pay, "buyer", pay_order=pay_order)
        self.my_orders = wrap(api.my_orders, "buyer", get_buyer_orders=get_orders)
        self.my_order = wrap(api.my_order, "buyer", get_buyer_orders=get_orders)

    def reserve_as(self, buyer, seats, *roles):
        body = json.dumps({"seats": [{"sector": s, "row": r, "number": n} for s, r, n in seats]})
        request = factory.post("/", data=body, content_type="application/json", HTTP_AUTHORIZATION=token(buyer, *roles))
        return self.reserve(request, event_id=DEMO_EVENT_ID)

    def pay_as(self, buyer, order_id):
        return self.pay(factory.post("/", HTTP_AUTHORIZATION=token(buyer)), order_id=UUID(order_id))


@pytest.fixture
def system():
    return System()


def test_events_list_matches_contract(system):
    response = system.list_events(factory.get("/", HTTP_AUTHORIZATION=token(uuid4(), "inspector")))

    assert_matches_contract(response, "get", "/events")
    [event] = json.loads(response.content)["events"]
    assert (event["seats_total"], event["seats_available"], event["price_from"]) == (56, 56, "600.00")


def test_hall_layout_matches_contract_and_unknown_event_is_404(system):
    found = system.hall(factory.get("/", HTTP_AUTHORIZATION=token(uuid4())), event_id=DEMO_EVENT_ID)
    missing = system.hall(factory.get("/", HTTP_AUTHORIZATION=token(uuid4())), event_id=uuid4())

    assert_matches_contract(found, "get", "/events/{event_id}")
    assert_matches_contract(missing, "get", "/events/{event_id}")
    assert (missing.status_code, json.loads(missing.content)["code"]) == (404, "not_found")


def test_reservation_is_made_for_buyer_from_token(system):
    buyer, other = uuid4(), uuid4()

    response = system.reserve_as(buyer, [("VIP", 1, 1), ("VIP", 1, 2)])

    assert_matches_contract(response, "post", "/events/{event_id}/reservations")
    assert response.status_code == 201
    mine = system.my_orders(factory.get("/", HTTP_AUTHORIZATION=token(buyer)))
    assert_matches_contract(mine, "get", "/orders")
    [order] = json.loads(mine.content)["orders"]
    assert (order["status"], order["total_amount"], len(order["seats"])) == ("AWAITING_PAYMENT", "3000.00", 2)
    assert json.loads(system.my_orders(factory.get("/", HTTP_AUTHORIZATION=token(other))).content)["orders"] == []


@pytest.mark.parametrize(
    ("body", "status", "code"),
    [({"seats": [{"sector": "VIP"}]}, 400, "invalid_request"), ({"seats": "VIP 1 1"}, 400, "invalid_request")],
)
def test_malformed_reservation_is_400(system, body, status, code):
    request = factory.post("/", data=json.dumps(body), content_type="application/json",
                           HTTP_AUTHORIZATION=token(uuid4()))
    response = system.reserve(request, event_id=DEMO_EVENT_ID)

    assert_matches_contract(response, "post", "/events/{event_id}/reservations")
    assert (response.status_code, json.loads(response.content)["code"]) == (status, code)


def test_taken_seat_and_limit_are_409_with_domain_codes(system):
    system.reserve_as(uuid4(), [("VIP", 1, 1)])
    taken = system.reserve_as(uuid4(), [("VIP", 1, 1)])
    too_many = system.reserve_as(uuid4(), [("Партер", 1, n) for n in range(1, 8)])

    for response in (taken, too_many):
        assert_matches_contract(response, "post", "/events/{event_id}/reservations")
    assert json.loads(taken.content)["code"] == "seat_not_available"
    assert json.loads(too_many.content)["code"] == "reservation_limit"


def test_only_buyers_can_reserve(system):
    response = system.reserve_as(uuid4(), [("VIP", 1, 1)], "organizer")

    assert_matches_contract(response, "post", "/events/{event_id}/reservations")
    assert response.status_code == 403


def test_owner_pays_once_and_others_cannot_see_or_pay_the_order(system):
    buyer = uuid4()
    order_id = json.loads(system.reserve_as(buyer, [("VIP", 1, 3)]).content)["order_id"]

    stranger_view = system.my_order(factory.get("/", HTTP_AUTHORIZATION=token(uuid4())), order_id=UUID(order_id))
    stranger_pay = system.pay_as(uuid4(), order_id)
    paid = system.pay_as(buyer, order_id)
    again = system.pay_as(buyer, order_id)

    assert_matches_contract(stranger_view, "get", "/orders/{order_id}")
    for response in (stranger_pay, paid, again):
        assert_matches_contract(response, "post", "/orders/{order_id}/payment")
    assert (stranger_view.status_code, stranger_pay.status_code) == (404, 404)
    assert json.loads(paid.content) == {"order_id": order_id, "status": "PAID"}
    assert (again.status_code, json.loads(again.content)["code"]) == (409, "order_already_paid")
    assert len(system.gateway.charges) == 1


NEW_EVENT = {
    "title": "Вечір джазу",
    "sales_start": "2026-11-01T10:00:00+02:00",
    "starts_at": "2026-12-31T19:00:00+02:00",
    "categories": [{"name": "Балкон", "price": "350"}, {"name": "Партер", "price": "800.50"}],
    "sectors": [{"name": "Партер", "rows": 2, "seats_per_row": 5}, {"name": "Балкон", "rows": 1, "seats_per_row": 4}],
}


def post_event(system, subject, body, *roles):
    request = factory.post("/", data=json.dumps(body), content_type="application/json",
                           HTTP_AUTHORIZATION=token(subject, *roles))
    return system.events(request)


def stats(system, subject, *roles):
    return system.organizer_events(factory.get("/", HTTP_AUTHORIZATION=token(subject, *roles)))


def test_organizer_creates_event_and_buyers_see_it(system):
    organizer = uuid4()

    created = post_event(system, organizer, NEW_EVENT, "organizer")
    listed = system.list_events(factory.get("/", HTTP_AUTHORIZATION=token(uuid4())))

    assert_matches_contract(created, "post", "/events")
    assert created.status_code == 201
    titles = [e["title"] for e in json.loads(listed.content)["events"]]
    assert "Вечір джазу" in titles
    event = next(e for e in json.loads(listed.content)["events"] if e["title"] == "Вечір джазу")
    assert (event["seats_total"], event["price_from"]) == (14, "350.00")


@pytest.mark.parametrize(
    ("change", "status", "code"),
    [
        ({"starts_at": "2026-10-01T19:00:00+02:00"}, 409, "invalid_event"),
        ({"starts_at": "2026-12-31T19:00:00"}, 400, "invalid_request"),
        ({"sectors": [{"name": "Ложа", "rows": 1, "seats_per_row": 2}]}, 409, "unknown_price_category"),
        ({"sectors": [{"name": "Партер", "rows": 500, "seats_per_row": 5}]}, 409, "invalid_event"),
        ({"categories": [{"name": "Партер", "price": "-1"}]}, 409, "invalid_money"),
    ],
    ids=["starts-before-sales", "naive-time", "unknown-category", "too-many-rows", "negative-price"],
)
def test_invalid_event_is_rejected(system, change, status, code):
    response = post_event(system, uuid4(), {**NEW_EVENT, **change}, "organizer")

    assert_matches_contract(response, "post", "/events")
    assert (response.status_code, json.loads(response.content)["code"]) == (status, code)


def test_buyer_cannot_create_events_or_see_sales(system):
    created = post_event(system, uuid4(), NEW_EVENT, "buyer")
    sales_stats = stats(system, uuid4(), "buyer")

    assert_matches_contract(created, "post", "/events")
    assert (created.status_code, sales_stats.status_code) == (403, 403)


def test_organizer_sees_sales_of_own_events_only_and_admin_sees_all(system):
    organizer, buyer = uuid4(), uuid4()
    event_id = json.loads(post_event(system, organizer, NEW_EVENT, "organizer").content)["event_id"]
    post_event(system, uuid4(), {**NEW_EVENT, "title": "Чужий захід"}, "organizer")
    body = json.dumps({"seats": [{"sector": "Партер", "row": 1, "number": 1}, {"sector": "Балкон", "row": 1,
                                                                                  "number": 1}]})
    reserved = system.reserve(factory.post("/", data=body, content_type="application/json",
                                           HTTP_AUTHORIZATION=token(buyer)), event_id=UUID(event_id))
    system.pay_as(buyer, json.loads(reserved.content)["order_id"])
    system.reserve(factory.post("/", data=json.dumps({"seats": [{"sector": "Партер", "row": 2, "number": 5}]}),
                                content_type="application/json", HTTP_AUTHORIZATION=token(uuid4())),
                   event_id=UUID(event_id))

    own = stats(system, organizer, "organizer")
    everything = stats(system, uuid4(), "admin")

    assert_matches_contract(own, "get", "/organizer/events")
    [event] = json.loads(own.content)["events"]
    assert (event["seats_total"], event["seats_sold"], event["seats_reserved"], event["seats_available"]) == (14, 2, 1, 11)
    assert (event["paid_orders"], event["revenue"]) == (1, "1150.50")
    assert len(json.loads(everything.content)["events"]) == 3, "демо-захід і два нові"


def test_unavailable_payment_service_is_503_and_declined_is_402():
    unavailable, declined = System(StubPaymentGateway(unavailable=True)), System(StubPaymentGateway(decline=True))
    buyer = uuid4()
    first = json.loads(unavailable.reserve_as(buyer, [("VIP", 1, 1)]).content)["order_id"]
    second = json.loads(declined.reserve_as(buyer, [("VIP", 1, 1)]).content)["order_id"]

    pending, refused = unavailable.pay_as(buyer, first), declined.pay_as(buyer, second)

    assert_matches_contract(pending, "post", "/orders/{order_id}/payment")
    assert_matches_contract(refused, "post", "/orders/{order_id}/payment")
    assert (pending.status_code, json.loads(pending.content)["code"]) == (503, "payment_unavailable")
    assert (refused.status_code, json.loads(refused.content)["code"]) == (402, "payment_declined")

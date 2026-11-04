"""Перевірка токена доступу від web (ADR-006): підпис, видавець, адресат, строк дії, ролі."""

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from django.test import RequestFactory

from tickets.presentation.auth import AuthError, authenticate, authenticated

SECRET = "test-secret-for-tkts-api--tokens-32b"
SUBJECT = uuid4()
factory = RequestFactory()


def token(secret=SECRET, sub=None, roles=("buyer",), minutes=5, **overrides):
    claims = {
        "sub": str(sub or SUBJECT),
        "roles": list(roles),
        "iss": "web",
        "aud": "ticketsales",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=minutes),
        **overrides,
    }
    return "Bearer " + jwt.encode(claims, secret, algorithm="HS256")


def test_valid_token_gives_subject_and_known_roles():
    principal = authenticate(token(roles=("buyer", "organizer", "superuser")), SECRET)

    assert principal.subject_id == SUBJECT
    assert principal.roles == {"buyer", "organizer"}, "невідомі ролі відкидаються"


@pytest.mark.parametrize(
    ("header", "code"),
    [
        (None, "unauthenticated"),
        ("Basic abc", "unauthenticated"),
        (token(secret="other-secret-that-web-never-uses-xx"), "invalid_token"),
        (token(minutes=-1), "token_expired"),
        (token(iss="evil"), "invalid_token"),
        (token(aud="other"), "invalid_token"),
        (token(sub="not-a-uuid"), "invalid_token"),
        ("Bearer not.a.jwt", "invalid_token"),
    ],
    ids=["no-header", "not-bearer", "wrong-secret", "expired", "wrong-issuer", "wrong-audience", "bad-subject",
         "garbage"],
)
def test_invalid_tokens_are_rejected_with_401(header, code):
    with pytest.raises(AuthError) as caught:
        authenticate(header, SECRET)

    assert (caught.value.status, caught.value.code) == (401, code)


def echo(request, *, principal):
    from django.http import JsonResponse

    return JsonResponse({"subject": str(principal.subject_id)})


def call(view, header):
    request = factory.get("/api/v1/x", HTTP_AUTHORIZATION=header) if header else factory.get("/api/v1/x")
    return view(request)


def test_wrapper_passes_principal_to_view():
    response = call(authenticated(echo, secret=SECRET), token())

    assert response.status_code == 200
    assert json.loads(response.content) == {"subject": str(SUBJECT)}


def test_wrapper_without_token_returns_401_in_contract_error_format():
    response = call(authenticated(echo, secret=SECRET), None)

    assert response.status_code == 401
    assert json.loads(response.content) == {"code": "unauthenticated", "message": "Потрібен токен доступу."}


def test_wrapper_without_required_role_returns_403():
    view = authenticated(echo, secret=SECRET, roles=("organizer", "admin"))

    assert call(view, token(roles=("buyer",))).status_code == 403
    assert call(view, token(roles=("admin",))).status_code == 200

"""Перевірка токена доступу від сервісу web (ADR-006).

Сервер web на кожен виклик JSON API підписує JWT (HS256, спільний секрет AUTH_TOKEN_SECRET) з
полями sub – subjectId користувача (UUID), roles – його ролі, iss = web, aud = ticketsales, exp.
Тут перевіряються підпис, видавець, адресат, строк дії й роль. Це шар presentation: сценарії й
домен отримують лише ідентифікатор користувача, про токени вони не знають.

Модуль повторює sales/presentation/auth.py, але не імпортує його: сервіси не ділять код.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from uuid import UUID

import jwt
from django.http import HttpRequest, JsonResponse

ISSUER = "web"
AUDIENCE = "ticketsales"
ROLES = frozenset({"buyer", "organizer", "inspector", "admin"})


@dataclass(frozen=True)
class Principal:
    """Користувач, від імені якого викликано API."""

    subject_id: UUID
    roles: frozenset[str]

    def has_any(self, roles: tuple[str, ...]) -> bool:
        return bool(self.roles & set(roles))


class AuthError(Exception):
    """Запит без дійсного токена (401) або без потрібної ролі (403)."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def authenticate(authorization: str | None, secret: str) -> Principal:
    """Principal із заголовка «Authorization: Bearer <JWT>» або AuthError(401)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthError(401, "unauthenticated", "Потрібен токен доступу.")
    try:
        claims = jwt.decode(
            authorization.removeprefix("Bearer "),
            secret,
            algorithms=["HS256"],
            audience=AUDIENCE,
            issuer=ISSUER,
            options={"require": ["exp", "sub", "iss", "aud"]},
        )
        subject_id = UUID(claims["sub"])
    except jwt.ExpiredSignatureError as exc:
        raise AuthError(401, "token_expired", "Строк дії токена минув.") from exc
    except (jwt.InvalidTokenError, ValueError) as exc:
        raise AuthError(401, "invalid_token", "Недійсний токен доступу.") from exc
    roles = claims.get("roles", [])
    if not isinstance(roles, list):
        raise AuthError(401, "invalid_token", "Недійсний токен доступу.")
    return Principal(subject_id, frozenset(role for role in roles if role in ROLES))


def error(status: int, code: str, message: str) -> JsonResponse:
    """Помилка у форматі Error контрактів: {"code", "message"}."""
    return JsonResponse({"code": code, "message": message}, status=status, json_dumps_params={"ensure_ascii": False})


def authenticated(view: Callable, *, secret: str, roles: tuple[str, ...] = ()) -> Callable:
    """Обгортка view: перевіряє токен і (якщо задано) одну з ролей, передає principal у view.

    Секрет передається явно з точки складання (urls.py), тож обгортку можна перевірити без
    налаштувань Django конкретного сервісу.
    """

    @wraps(view)
    def wrapper(request: HttpRequest, *args, **kwargs):
        try:
            principal = authenticate(request.headers.get("Authorization"), secret)
            if roles and not principal.has_any(roles):
                raise AuthError(403, "forbidden", "Недостатньо прав для цієї дії.")
        except AuthError as exc:
            return error(exc.status, exc.code, exc.message)
        return view(request, *args, principal=principal, **kwargs)

    return wrapper


def read_json(request: HttpRequest) -> dict:
    """Тіло запиту JSON; некоректне – ValueError."""
    data = json.loads(request.body or b"{}")
    if not isinstance(data, dict):
        raise ValueError("Тіло запиту має бути об'єктом JSON.")
    return data

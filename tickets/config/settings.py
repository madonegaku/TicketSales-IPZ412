"""Налаштування Django для сервісу tickets (ЛР 3).

Мінімальний набір: сервісу не потрібні адмін-панель, автентифікація й сесії Django,
тому вбудовані застосунки з таблицями не підключено. Свої дані tickets зберігає
у власному сховищі (інфраструктурний шар), а не в спільній базі даних.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Значення за замовчуванням – лише для розробки; при розгортанні задаються змінними середовища.
SECRET_KEY = os.environ.get("TICKETS_SECRET_KEY", "django-insecure-tickets-dev-only")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "tickets"]

INSTALLED_APPS = [
    "tickets.presentation",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "tickets.config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
    },
]

DATABASES = {}

LANGUAGE_CODE = "uk"
TIME_ZONE = "Europe/Kyiv"
USE_I18N = True
USE_TZ = True

# Захід, на вході якого працює контролер (Inspector); у ЛР 3 – демонстраційний концерт.
INSPECTOR_EVENT_ID = os.environ.get("INSPECTOR_EVENT_ID", "00000000-0000-0000-0000-000000000018")

# Власна база tickets – файл SQLite; спільна для веб-процесу й процесу-споживача цього ж сервісу.
TICKETS_DB_PATH = os.environ.get("TICKETS_DB_PATH", str(BASE_DIR / "tickets.sqlite3"))

# Брокер подій Redis (Streams); у Docker адресу задає змінна середовища.
REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")

# Секрет підпису токенів доступу від сервісу web (ADR-006); спільний для web, sales і tickets.
# Значення за замовчуванням – лише для розробки; у Docker задає змінна середовища.
AUTH_TOKEN_SECRET = os.environ.get("AUTH_TOKEN_SECRET", "dev-only-change-me-ticketsales-web-token")
"""Налаштування Django для сервісу payments (ЛР 3): лише JSON API для sales, без HTML, сесій і бази Django."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Значення за замовчуванням – лише для розробки; при розгортанні задаються змінними середовища.
SECRET_KEY = os.environ.get("PAYMENTS_SECRET_KEY", "django-insecure-payments-dev-only")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "payments"]

INSTALLED_APPS = []

# CSRF-захист не потрібен: API викликає інший сервіс, а не браузер із cookie.
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "payments.config.urls"

DATABASES = {}

LANGUAGE_CODE = "uk"
TIME_ZONE = "Europe/Kyiv"
USE_I18N = True
USE_TZ = True

# Власна база payments – файл SQLite (у Docker – у томі сервісу).
PAYMENTS_DB_PATH = os.environ.get("PAYMENTS_DB_PATH", str(BASE_DIR / "payments.sqlite3"))

# Імітація провайдера для експериментів: причина відмови або збій.
PROVIDER_DECLINE_REASON = os.environ.get("PROVIDER_DECLINE_REASON") or None
PROVIDER_UNAVAILABLE = os.environ.get("PROVIDER_UNAVAILABLE", "0") == "1"
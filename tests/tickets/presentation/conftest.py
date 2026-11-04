"""Мінімальні налаштування Django для тестів шару presentation tickets.

View викликаються напряму з RequestFactory, без маршрутів і бази, тож потрібні лише базові
налаштування. Django налаштовується раз на процес: якщо інші тести (payments) уже це зробили,
використовуються їхні налаштування – view tickets від них не залежать.
"""

import django
from django.conf import settings

if not settings.configured:
    settings.configure(ALLOWED_HOSTS=["testserver"], USE_TZ=True, DEFAULT_CHARSET="utf-8")
    django.setup()

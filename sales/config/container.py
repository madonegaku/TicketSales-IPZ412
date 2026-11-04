"""Контейнер залежностей веб-процесу sales: один на процес, з налаштуваннями Django.

Сам клас Container і правила складання – у config/composition.py. Тут створюється
екземпляр і запускається фоновий «поштар» вихідної черги.
"""

from django.conf import settings

from sales.config.composition import Container

container = Container(settings)
container.outbox_relay.start()

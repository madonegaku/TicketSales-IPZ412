"""Точка входу процесу-споживача подій OrderPaid сервісу tickets.

Запуск: python -m tickets.config.consumer – окремий процес поруч із веб-процесом tickets.
"""

import logging
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tickets.config.settings")
django.setup()

from tickets.config.container import container  # noqa: E402

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger.info("Споживач OrderPaid запущено – очікування подій.")
    try:
        container.order_paid_consumer.run_forever()
    except KeyboardInterrupt:
        logger.info("Споживач зупинено.")


if __name__ == "__main__":
    main()
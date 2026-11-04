"""Адаптер redis-py до групи споживачів потоку (патерн Adapter).

Споживачеві подій потрібні три прості дії: створити групу, прочитати порцію повідомлень і
підтвердити повідомлення. redis-py дає для цього незручний інтерфейс: відповідь XREADGROUP –
вкладені списки [[потік, [(id, поля), …]]], наявна група – помилка з текстом «BUSYGROUP»,
обрив з'єднання – власний виняток бібліотеки. Адаптер приховує ці деталі за власним
інтерфейсом, тож лише він знає про бібліотеку redis.
"""

from dataclasses import dataclass

import redis


class BrokerUnavailableError(Exception):
    """Брокер повідомлень недоступний (обрив з'єднання з Redis) – операцію можна повторити пізніше."""


@dataclass(frozen=True)
class StreamMessage:
    """Повідомлення потоку: ідентифікатор для підтвердження й поля запису."""

    message_id: str
    fields: dict


class RedisConsumerGroup:
    """Учасник групи споживачів одного потоку Redis Streams."""

    def __init__(self, client: redis.Redis, stream: str, group: str, consumer_name: str) -> None:
        self._client = client
        self._stream = stream
        self._group = group
        self._consumer_name = consumer_name

    def ensure_exists(self) -> None:
        """Створює групу з першого повідомлення потоку (і сам потік), якщо її ще немає."""
        try:
            self._client.xgroup_create(self._stream, self._group, id="0", mkstream=True)
        except redis.ConnectionError as exc:
            raise BrokerUnavailableError(str(exc)) from exc
        except redis.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    def read(self, start_id: str = ">", block_ms: int | None = 5000, count: int = 10) -> list[StreamMessage]:
        """Порція повідомлень: «>» – нові, «0» – власні непідтверджені; block_ms=None – без очікування."""
        try:
            response = self._client.xreadgroup(
                self._group, self._consumer_name, {self._stream: start_id}, count=count, block=block_ms
            )
        except redis.ConnectionError as exc:
            raise BrokerUnavailableError(str(exc)) from exc
        return [
            StreamMessage(message_id, fields)
            for _stream, entries in response or []
            for message_id, fields in entries
        ]

    def ack(self, message_id: str) -> None:
        """Підтверджує обробку: повідомлення більше не повертається цьому учаснику групи."""
        try:
            self._client.xack(self._stream, self._group, message_id)
        except redis.ConnectionError as exc:
            raise BrokerUnavailableError(str(exc)) from exc

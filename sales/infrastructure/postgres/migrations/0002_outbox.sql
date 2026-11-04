-- 0002 – вихідна черга подій (transactional outbox) у базі sales.
-- Подія OrderPaid додається в тій самій транзакції, що й статус «оплачене»: або обидва
-- записи є, або жодного (закриває борг ЛР 3 – черга в пам'яті губила події при перезапуску).
-- «Поштар» читає неопубліковані події в порядку position і позначає опубліковані published_at;
-- рядок не видаляється одразу, щоб можна було перевірити, що й коли опубліковано.
CREATE TABLE outbox (
    message_id UUID PRIMARY KEY,
    position BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE,
    message_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at TIMESTAMPTZ
);

-- Частковий індекс: «поштар» щосекунди шукає лише неопубліковані події.
CREATE INDEX outbox_pending ON outbox (position) WHERE published_at IS NULL;

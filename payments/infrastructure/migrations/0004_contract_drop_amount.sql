-- 0004 – СКОРОЧЕННЯ: вилучення старої структури.
-- Виконується лише тоді, коли всі екземпляри payments працюють на версії, що пише й читає
-- тільки amount_minor: стовпець amount уже ніхто не використовує.
-- Водночас amount_minor стає обов'язковим. Якщо якийсь рядок досі без копійок (0003 не
-- виконано), INSERT порушить NOT NULL і вся міграція відкотиться – дані не втратяться.
-- SQLite не змінює обмеження наявних стовпців, тому таблицю знову перебудовано
-- (у PostgreSQL – ALTER COLUMN amount_minor SET NOT NULL і DROP COLUMN amount).
CREATE TABLE payments_0004 (
    order_id TEXT PRIMARY KEY,
    payment_id TEXT NOT NULL UNIQUE,
    amount_minor INTEGER NOT NULL CHECK (amount_minor >= 0),
    currency TEXT NOT NULL,
    status TEXT NOT NULL,
    decline_reason TEXT,
    created_at TEXT NOT NULL
);

INSERT INTO payments_0004 (order_id, payment_id, amount_minor, currency, status, decline_reason, created_at)
SELECT order_id, payment_id, amount_minor, currency, status, decline_reason, created_at FROM payments;

DROP TABLE payments;
ALTER TABLE payments_0004 RENAME TO payments;

-- 0002 – РОЗШИРЕННЯ: нова структура поруч зі старою.
-- Сума зберігатиметься цілим числом копійок (amount_minor) замість тексту (amount):
-- цілі числа SQLite порівнює й підсумовує точно, текст – ні (звірка платежів, звіти).
--
-- Обидва стовпці тимчасово допускають NULL: попередня версія коду пише лише amount, а
-- версія після скорочення писатиме лише amount_minor – обидві мають працювати з цією схемою.
-- SQLite не вміє знімати NOT NULL з наявного стовпця, тому таблицю перебудовано
-- (у PostgreSQL це було б ALTER COLUMN amount DROP NOT NULL і ADD COLUMN amount_minor).
CREATE TABLE payments_0002 (
    order_id TEXT PRIMARY KEY,
    payment_id TEXT NOT NULL UNIQUE,
    amount TEXT,
    amount_minor INTEGER CHECK (amount_minor >= 0),
    currency TEXT NOT NULL,
    status TEXT NOT NULL,
    decline_reason TEXT,
    created_at TEXT NOT NULL,
    CHECK (amount IS NOT NULL OR amount_minor IS NOT NULL)
);

INSERT INTO payments_0002 (order_id, payment_id, amount, currency, status, decline_reason, created_at)
SELECT order_id, payment_id, amount, currency, status, decline_reason, created_at FROM payments;

DROP TABLE payments;
ALTER TABLE payments_0002 RENAME TO payments;

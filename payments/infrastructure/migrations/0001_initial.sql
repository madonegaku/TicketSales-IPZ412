-- 0001 – базова схема платежів (стан після ЛР 3).
-- IF NOT EXISTS: у базах, створених до появи міграцій, таблиця вже є – міграція лише фіксує версію.
CREATE TABLE IF NOT EXISTS payments (
    order_id TEXT PRIMARY KEY,
    payment_id TEXT NOT NULL UNIQUE,
    amount TEXT NOT NULL,
    currency TEXT NOT NULL,
    status TEXT NOT NULL,
    decline_reason TEXT,
    created_at TEXT NOT NULL
);

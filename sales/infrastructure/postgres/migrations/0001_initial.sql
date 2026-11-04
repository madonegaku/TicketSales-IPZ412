-- 0001 – початкова схема sales (PostgreSQL 16): агрегати Event, Reservation, Order.
--
-- Правила схеми:
-- * кожен агрегат – головна таблиця й таблиці його внутрішніх частин (місця, рядки);
-- * зовнішні ключі – лише всередині бази sales; buyer_id – ідентифікатор без зовнішнього
--   ключа: покупець не має сервісу-власника (автентифікації ще немає);
-- * стани зберігаються стабільними кодами (AVAILABLE, PAID), а не текстом інтерфейсу з домену
--   («вільне», «оплачене»): зміна формулювання не повинна змінювати дані;
-- * гроші – NUMERIC(12, 2) і код валюти: точно, як Decimal у домені.

CREATE TABLE events (
    id UUID PRIMARY KEY,
    title TEXT NOT NULL CHECK (title <> ''),
    sales_start TIMESTAMPTZ NOT NULL,
    starts_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE price_categories (
    event_id UUID NOT NULL REFERENCES events (id),
    name TEXT NOT NULL,
    price_amount NUMERIC(12, 2) NOT NULL CHECK (price_amount >= 0),
    price_currency CHAR(3) NOT NULL,
    PRIMARY KEY (event_id, name)
);

CREATE TABLE seats (
    event_id UUID NOT NULL REFERENCES events (id),
    sector TEXT NOT NULL,
    seat_row INTEGER NOT NULL CHECK (seat_row >= 1),
    seat_number INTEGER NOT NULL CHECK (seat_number >= 1),
    ordinal INTEGER NOT NULL,
    category TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('AVAILABLE', 'RESERVED', 'SOLD')),
    PRIMARY KEY (event_id, sector, seat_row, seat_number),
    UNIQUE (event_id, ordinal),
    FOREIGN KEY (event_id, category) REFERENCES price_categories (event_id, name)
);

CREATE TABLE reservations (
    id UUID PRIMARY KEY,
    event_id UUID NOT NULL REFERENCES events (id),
    buyer_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

-- Запит ліміту С-06: місця покупця на захід у непрострочених резервуваннях.
CREATE INDEX reservations_by_buyer ON reservations (buyer_id, event_id, created_at);

CREATE TABLE reservation_seats (
    reservation_id UUID NOT NULL REFERENCES reservations (id),
    line_no INTEGER NOT NULL,
    sector TEXT NOT NULL,
    seat_row INTEGER NOT NULL,
    seat_number INTEGER NOT NULL,
    PRIMARY KEY (reservation_id, line_no)
);

CREATE TABLE orders (
    id UUID PRIMARY KEY,
    reservation_id UUID NOT NULL UNIQUE REFERENCES reservations (id),
    event_id UUID NOT NULL REFERENCES events (id),
    payment_deadline TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('AWAITING_PAYMENT', 'PAYMENT_PENDING', 'PAID'))
);

CREATE TABLE order_lines (
    order_id UUID NOT NULL REFERENCES orders (id),
    line_no INTEGER NOT NULL,
    sector TEXT NOT NULL,
    seat_row INTEGER NOT NULL,
    seat_number INTEGER NOT NULL,
    price_amount NUMERIC(12, 2) NOT NULL CHECK (price_amount >= 0),
    price_currency CHAR(3) NOT NULL,
    PRIMARY KEY (order_id, line_no)
);

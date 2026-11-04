-- 0003 – РОЗШИРЕННЯ: покупець замовлення (ADR-006 – «Мої замовлення», оплатити може лише власник).
-- Стовпець допускає NULL: попередня версія коду (ЛР 5) не пише buyer_id і має працювати й далі.
-- Наявні замовлення отримують покупця з резервування, за яким їх створено.
ALTER TABLE orders ADD COLUMN buyer_id UUID;

UPDATE orders o SET buyer_id = r.buyer_id
FROM reservations r
WHERE r.id = o.reservation_id AND o.buyer_id IS NULL;

CREATE INDEX orders_by_buyer ON orders (buyer_id);

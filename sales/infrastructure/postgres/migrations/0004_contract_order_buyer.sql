-- 0004 – СКОРОЧЕННЯ: покупець замовлення обов'язковий.
-- Виконується, коли всі екземпляри sales пишуть buyer_id. Замовлення, які попередня версія
-- встигла створити після 0003, спершу отримують покупця з резервування – лише тоді NOT NULL.
UPDATE orders o SET buyer_id = r.buyer_id
FROM reservations r
WHERE r.id = o.reservation_id AND o.buyer_id IS NULL;

ALTER TABLE orders ALTER COLUMN buyer_id SET NOT NULL;

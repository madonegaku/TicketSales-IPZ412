-- 0005 – організатор заходу (ADR-006). Лише розширення: стовпець лишається необов'язковим, бо
-- демо-захід ЛР 2 створено системою, без організатора. Попередня версія коду, що не пише
-- organizer_id, працює й після цієї міграції.
ALTER TABLE events ADD COLUMN organizer_id UUID;

CREATE INDEX events_by_organizer ON events (organizer_id);

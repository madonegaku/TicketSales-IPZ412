# Образ одного сервісу системи; який саме – задає аргумент SERVICE (sales, payments або tickets).
# Кожен образ містить лише код свого сервісу: сервіси збираються й розгортаються незалежно.
FROM python:3.12-slim

ARG SERVICE
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ${SERVICE}/ ./${SERVICE}/

EXPOSE 8000
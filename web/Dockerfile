# Образ сервісу web (Meteor 3, ADR-006) у два етапи:
# 1) збірка: інструмент Meteor збирає застосунок у звичайний Node-пакет (meteor build);
# 2) запуск: лише Node.js тієї версії, з якою працює Meteor 3.5.4, без інструменту Meteor.
FROM node:24.22.1-bookworm AS build

ENV METEOR_ALLOW_SUPERUSER=true \
    METEOR_DISABLE_OPTIMISTIC_CACHING=1
RUN npx --yes meteor@3.5.4 \
    && ln -s /root/.meteor/meteor /usr/local/bin/meteor

WORKDIR /app
COPY package.json package-lock.json ./
RUN meteor npm ci
COPY . .
RUN meteor build --directory /build --server-only

FROM node:24.22.1-bookworm-slim

WORKDIR /app
COPY --from=build /build/bundle ./
RUN cd programs/server && npm install --omit=dev

ENV PORT=3000 \
    NODE_ENV=production
EXPOSE 3000
CMD ["node", "main.js"]

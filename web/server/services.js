// Виклики JSON API sales і tickets від імені користувача (ADR-006, «бекенд для фронтенду»).
// Браузер ніколи не звертається до сервісів напряму: сервер web підписує короткий JWT із
// subjectId і ролями користувача, а сервіси перевіряють підпис, строк дії й роль.
import jwt from "jsonwebtoken";
import { Meteor } from "meteor/meteor";
import { ROLES } from "/imports/api/roles";

const SECRET = process.env.AUTH_TOKEN_SECRET || "dev-only-change-me-ticketsales-web-token";
export const SALES_API = process.env.SALES_API_URL || "http://127.0.0.1:8100/api/v1";
export const TICKETS_API = process.env.TICKETS_API_URL || "http://127.0.0.1:8200/api/v1";
const TIMEOUT_MS = 5000; // оплата всередині sales чекає payments до 2 с

export function tokenFor(user, roles) {
  return jwt.sign({ roles: roles.filter((role) => ROLES.includes(role)) }, SECRET, {
    algorithm: "HS256",
    subject: user.subjectId,
    issuer: "web",
    audience: "ticketsales",
    expiresIn: "5m",
  });
}

export async function callApi(base, method, path, { user, roles }, body) {
  let response;
  try {
    response = await fetch(base + path, {
      method,
      headers: { Authorization: `Bearer ${tokenFor(user, roles)}`, "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch (error) {
    console.warn(`Сервіс недоступний: ${method} ${base}${path} – ${error.message}`);
    throw new Meteor.Error("service_unavailable", "Сервіс тимчасово недоступний. Спробуйте ще раз за хвилину.");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (!data.code) console.warn(`Неочікувана відповідь: ${method} ${base}${path} – HTTP ${response.status}`);
    throw new Meteor.Error(data.code || `http_${response.status}`, data.message || `Помилка сервісу (HTTP ${response.status}).`);
  }
  return data;
}

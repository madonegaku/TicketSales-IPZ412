// Методи Meteor, які викликає інтерфейс. Кожен перевіряє вхід і роль, а дані бере з sales і
// tickets – web не зберігає копій заходів, замовлень чи квитків (матриця володіння, ADR-006).
import { Accounts } from "meteor/accounts-base";
import { check, Match } from "meteor/check";
import { Meteor } from "meteor/meteor";
import { Roles } from "meteor/roles";
import { ROLES } from "/imports/api/roles";
import { callApi, SALES_API, TICKETS_API } from "./services";

const Id = Match.Where((value) => typeof value === "string" && /^[0-9a-f-]{36}$/i.test(value));

async function requireUser(context, ...allowed) {
  if (!context.userId) throw new Meteor.Error("unauthenticated", "Увійдіть у систему.");
  const user = await Meteor.users.findOneAsync(context.userId);
  if (!user || user.blocked) throw new Meteor.Error("blocked", "Обліковий запис заблоковано.");
  const roles = await Roles.getRolesForUserAsync(user._id);
  if (allowed.length && !allowed.some((role) => roles.includes(role))) {
    throw new Meteor.Error("forbidden", "Недостатньо прав для цієї дії.");
  }
  return { user, roles };
}

Meteor.methods({
  async "auth.register"({ name, email, password }) {
    check(name, String);
    check(email, String);
    check(password, String);
    if (password.length < 8) throw new Meteor.Error("weak_password", "Пароль має містити щонайменше 8 символів.");
    if (!/^[^@\s]+@[^@\s]+$/.test(email)) throw new Meteor.Error("invalid_email", "Некоректна адреса пошти.");
    if (await Accounts.findUserByEmail(email)) throw new Meteor.Error("email_taken", "Користувач із такою поштою вже є.");
    const userId = await Accounts.createUserAsync({ email, password, profile: { name } });
    await Roles.addUsersToRolesAsync(userId, ["buyer"]);
    return userId;
  },

  // ---- Афіша й схема залу: будь-яка роль ----
  async "events.list"() {
    return (await callApi(SALES_API, "GET", "/events", await requireUser(this))).events;
  },

  async "events.hall"(eventId) {
    check(eventId, Id);
    return callApi(SALES_API, "GET", `/events/${eventId}`, await requireUser(this));
  },

  // ---- Покупець ----
  async "orders.reserve"(eventId, seats) {
    check(eventId, Id);
    check(seats, [{ sector: String, row: Match.Integer, number: Match.Integer }]);
    return callApi(SALES_API, "POST", `/events/${eventId}/reservations`, await requireUser(this, "buyer"), { seats });
  },

  async "orders.pay"(orderId) {
    check(orderId, Id);
    return callApi(SALES_API, "POST", `/orders/${orderId}/payment`, await requireUser(this, "buyer"));
  },

  async "orders.mine"() {
    return (await callApi(SALES_API, "GET", "/orders", await requireUser(this, "buyer"))).orders;
  },

  async "orders.tickets"(orderId) {
    check(orderId, Id);
    const caller = await requireUser(this, "buyer");
    // tickets не знає покупця замовлення: власника перевіряє sales (чуже замовлення – 404).
    const order = await callApi(SALES_API, "GET", `/orders/${orderId}`, caller);
    const { tickets } = await callApi(TICKETS_API, "GET", `/orders/${orderId}/tickets`, caller);
    return { order, tickets };
  },

  // ---- Організатор ----
  async "organizer.createEvent"(form) {
    check(form, {
      title: String,
      sales_start: String,
      starts_at: String,
      categories: [{ name: String, price: String }],
      sectors: [{ name: String, rows: Match.Integer, seats_per_row: Match.Integer, category: String }],
    });
    const caller = await requireUser(this, "organizer", "admin");
    return (await callApi(SALES_API, "POST", "/events", caller, form)).event_id;
  },

  async "organizer.events"() {
    return (await callApi(SALES_API, "GET", "/organizer/events", await requireUser(this, "organizer", "admin"))).events;
  },

  // ---- Контролер ----
  async "inspector.validate"(code, eventId) {
    check(code, String);
    check(eventId, Id);
    const caller = await requireUser(this, "inspector", "admin");
    return callApi(TICKETS_API, "POST", "/validations", caller, { code: code.trim(), event_id: eventId });
  },

  // ---- Адміністратор ----
  async "admin.users"() {
    await requireUser(this, "admin");
    const users = await Meteor.users.find({}, { sort: { createdAt: -1 } }).fetchAsync();
    return Promise.all(users.map(async (user) => ({
      id: user._id,
      name: user.profile?.name ?? "",
      email: user.emails?.[0]?.address ?? "",
      roles: await Roles.getRolesForUserAsync(user._id),
      blocked: Boolean(user.blocked),
      createdAt: user.createdAt,
    })));
  },

  async "admin.setRoles"(userId, roles) {
    check(userId, String);
    check(roles, [Match.OneOf(...ROLES)]);
    await requireUser(this, "admin");
    if (userId === this.userId && !roles.includes("admin")) {
      throw new Meteor.Error("self_demotion", "Не можна зняти роль адміністратора із себе.");
    }
    await Roles.setUserRolesAsync(userId, roles);
  },

  async "admin.setBlocked"(userId, blocked) {
    check(userId, String);
    check(blocked, Boolean);
    await requireUser(this, "admin");
    if (userId === this.userId) throw new Meteor.Error("self_block", "Не можна заблокувати себе.");
    // Блокування одразу завершує всі сеанси користувача.
    const changes = blocked ? { $set: { blocked, "services.resume.loginTokens": [] } } : { $set: { blocked } };
    await Meteor.users.updateAsync(userId, changes);
  },
});

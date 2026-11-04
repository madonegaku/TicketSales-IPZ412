// Облікові записи й ролі – дані, якими володіє web (ADR-006).
// Кожен користувач має subjectId (UUID) – під цим ідентифікатором його знають sales і tickets
// (buyer_id замовлення, organizer_id заходу). Внутрішній _id Meteor назовні не передається.
import { randomUUID } from "node:crypto";
import { Accounts } from "meteor/accounts-base";
import { DDPRateLimiter } from "meteor/ddp-rate-limiter";
import { Meteor } from "meteor/meteor";
import { Roles } from "meteor/roles";
import { ROLES } from "/imports/api/roles";

// Реєстрація – лише через метод auth.register: він одразу видає роль покупця.
Accounts.config({ forbidClientAccountCreation: true, loginExpirationInDays: 7 });

Accounts.onCreateUser((options, user) => ({
  ...user,
  profile: { name: String(options.profile?.name ?? "").trim() },
  subjectId: randomUUID(),
  blocked: false,
}));

Accounts.validateLoginAttempt(({ allowed, user }) => {
  if (allowed && user?.blocked) {
    throw new Meteor.Error("blocked", "Обліковий запис заблоковано адміністратором.");
  }
  return allowed;
});

// Не більше 5 спроб входу чи реєстрації за 10 с з одного з'єднання (захист від перебору паролів).
DDPRateLimiter.addRule({ type: "method", name: (name) => ["login", "auth.register"].includes(name) }, 5, 10_000);

// Поточному користувачу – власні поля й призначення ролей (для меню за ролями).
Meteor.publish("me", function publishMe() {
  if (!this.userId) return this.ready();
  return Meteor.users.find(this.userId, { fields: { subjectId: 1, blocked: 1, profile: 1, emails: 1 } });
});

Meteor.publish(null, function publishOwnRoles() {
  if (!this.userId) return this.ready();
  return Meteor.roleAssignment.find({ "user._id": this.userId });
});

async function ensureUser(email, password, name, roles) {
  const existing = await Accounts.findUserByEmail(email);
  if (existing) return;
  const userId = await Accounts.createUserAsync({ email, password, profile: { name } });
  await Roles.addUsersToRolesAsync(userId, roles);
  console.log(`Створено користувача ${email} з ролями ${roles.join(", ")}`);
}

Meteor.startup(async () => {
  for (const role of ROLES) {
    await Roles.createRoleAsync(role, { unlessExists: true });
  }
  // Перший адміністратор – зі змінних середовища; значення за замовчуванням лише для розробки.
  await ensureUser(
    process.env.ADMIN_EMAIL || "admin@ticketsales.local",
    process.env.ADMIN_PASSWORD || "admin-dev-password",
    "Адміністратор",
    ["admin"],
  );
  // Демонстраційні користувачі всіх ролей (SEED_DEMO_USERS=1) – для показу й ручної перевірки.
  if (process.env.SEED_DEMO_USERS === "1") {
    await ensureUser("organizer@ticketsales.local", "organizer-dev-password", "Організатор Демо", ["organizer"]);
    await ensureUser("inspector@ticketsales.local", "inspector-dev-password", "Контролер Демо", ["inspector"]);
    await ensureUser("buyer@ticketsales.local", "buyer-dev-password", "Покупець Демо", ["buyer"]);
  }
});

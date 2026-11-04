export function formatDate(iso) {
  return new Date(iso).toLocaleString("uk-UA", { dateStyle: "medium", timeStyle: "short" });
}

export function formatMoney(amount, currency = "UAH") {
  const value = Number(amount).toLocaleString("uk-UA", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return currency === "UAH" ? `${value} грн` : `${value} ${currency}`;
}

export const ORDER_STATUS = {
  AWAITING_PAYMENT: "Очікує оплати",
  PAYMENT_PENDING: "Оплата обробляється",
  PAID: "Оплачено",
};

export const TICKET_STATUS = { VALID: "Дійсний", USED: "Використаний", REFUNDED: "Повернений" };

export { formatMinorMoney as money } from "../../../lib/money";
export const reasonIsValid = (value: string) => /^[a-z][a-z0-9_]{0,63}$/.test(value);
/** datetime-local is deliberately labelled UTC; never interpret it in the browser timezone. */
export function utcInstant(value: string) {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,3})?)?$/.test(value)) return null;
  const date = new Date(`${value}Z`);
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 16) === value.slice(0, 16)
    ? date.toISOString().replace(/\.000Z$/, "Z") : null;
}
export const scopeIdentity = (actorId: number, makerspaceId?: number) => `${window.location.host}:${actorId}:${makerspaceId ?? "member"}`;

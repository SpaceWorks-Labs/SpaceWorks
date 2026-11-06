// The one locale runtime (phase 8 i18n): which language the app renders in, where that
// choice came from, and the headers that tell the API.
//
// Precedence, highest first: a valid `?lang=` on the URL or a stored in-app choice
// (`explicit`), the signed-in account's preference (`user`), the tenant bootstrap default
// (`makerspace`), then `en` (`system`). Only an explicit choice is ever sent as
// `X-SpaceWorks-Locale`; the effective locale always travels as `Accept-Language`.
//
// This module activates Lingui when it is first imported, so `main.tsx` imports it before
// anything that renders text. Copy evaluated at module load (labels in a constant) keeps the
// locale it loaded in; a change of effective locale therefore reloads the page once, and the
// last effective locale is remembered so the next load starts in it (no reload loop).
import { i18n, type Messages } from "@lingui/core";
import { messages as en } from "../locales/en/messages.po";
import { SUPPORTED_LOCALES, SYSTEM_LOCALE, type LocaleCode } from "../generated/locales";
import { readStorage, removeStorage, writeStorage } from "./safeStorage";

export type LocaleSource = "explicit" | "user" | "makerspace" | "system";

const CATALOGS: Record<LocaleCode, Messages> = { en };
const EXPLICIT_KEY = "spaceworks.locale";
const EFFECTIVE_KEY = "spaceworks.locale.effective";
const CODES: readonly string[] = SUPPORTED_LOCALES.map((locale) => locale.code);

/** The registry code for a case/underscore/region variant, else null (mirrors the backend). */
export function canonicalLocale(value: unknown): LocaleCode | null {
  if (typeof value !== "string") return null;
  const candidate = value.trim().replace(/_/g, "-").toLowerCase();
  if (!/^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$/.test(candidate)) return null;
  if (CODES.includes(candidate)) return candidate as LocaleCode;
  const base = candidate.split("-")[0];
  return CODES.includes(base) ? (base as LocaleCode) : null;
}

function urlLocale(): LocaleCode | null {
  try {
    return canonicalLocale(new URLSearchParams(window.location.search).get("lang"));
  } catch {
    return null;
  }
}

let explicit: LocaleCode | null = urlLocale() ?? canonicalLocale(readStorage(EXPLICIT_KEY));
if (explicit && urlLocale()) writeStorage(EXPLICIT_KEY, explicit);
let userLocale: LocaleCode | null = null;
let makerspaceLocale: LocaleCode | null = null;
const listeners = new Set<() => void>();

function resolveLocale(): { code: LocaleCode; source: LocaleSource } {
  if (explicit) return { code: explicit, source: "explicit" };
  if (userLocale) return { code: userLocale, source: "user" };
  if (makerspaceLocale) return { code: makerspaceLocale, source: "makerspace" };
  return { code: SYSTEM_LOCALE, source: "system" };
}

let current = resolveLocale();
// Before session/bootstrap data arrives, start in the last effective locale.
const startup: LocaleCode = explicit ?? canonicalLocale(readStorage(EFFECTIVE_KEY)) ?? SYSTEM_LOCALE;
i18n.load(CATALOGS);
i18n.activate(startup);

function recompute() {
  const next = resolveLocale();
  const changed = next.code !== current.code || next.source !== current.source;
  current = next;
  if (!changed) return;
  writeStorage(EFFECTIVE_KEY, next.code);
  if (next.code !== i18n.locale) {
    i18n.activate(next.code);
    if (next.code !== startup && typeof window !== "undefined" && import.meta.env.MODE !== "test") window.location.reload();
  }
  listeners.forEach((listener) => listener());
}

export const activeLocale = (): LocaleCode => current.code;
export const localeSource = (): LocaleSource => current.source;
export const explicitLocale = (): LocaleCode | null => explicit;

/** Subscribe to effective-locale changes; returns the unsubscribe function. */
export function onLocaleChange(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** A deliberate in-app choice (`null` clears it and drops `?lang=` from the URL). */
export function setExplicitLocale(code: string | null) {
  const next = code === null ? null : canonicalLocale(code);
  if (code !== null && next === null) return;
  explicit = next;
  if (next) {
    writeStorage(EXPLICIT_KEY, next);
  } else {
    removeStorage(EXPLICIT_KEY);
    try {
      const url = new URL(window.location.href);
      if (url.searchParams.has("lang")) {
        url.searchParams.delete("lang");
        window.history.replaceState(window.history.state, "", url.toString());
      }
    } catch {
      // A sandboxed or detached window has no history to edit.
    }
  }
  recompute();
}

/** Session hydration: the account's own preference (null follows the makerspace). */
export function setUserLocale(code: string | null | undefined) {
  userLocale = canonicalLocale(code);
  recompute();
}

/** Tenant bootstrap: the makerspace default. */
export function setMakerspaceLocale(code: string | null | undefined) {
  makerspaceLocale = canonicalLocale(code);
  recompute();
}

/** Headers for every SpaceWorks API request; never for signed object-storage URLs. */
export function localeHeaders(): Record<string, string> {
  const { code, source } = current;
  return source === "explicit" ? { "Accept-Language": code, "X-SpaceWorks-Locale": code } : { "Accept-Language": code };
}

/** Apply the validated locale headers AFTER the caller's own, so they cannot be forged. */
export function withLocaleHeaders(headers?: HeadersInit): Headers {
  const merged = new Headers(headers);
  merged.delete("X-SpaceWorks-Locale");
  for (const [name, value] of Object.entries(localeHeaders())) merged.set(name, value);
  return merged;
}

export { i18n };

import { t } from "@lingui/core/macro";
// Card number patterns, checked in the browser so the desk sees a problem (and the next
// numbers) as it types. The server (apps/card_designs/numbering.py) is the authority and
// repeats every rule; this file only mirrors it for instant feedback.

export const MAX_NUMBER_LENGTH = 32;
const TOKEN = /\{(PREFIX|SEQ|MEMBER|YYYY|YY|UNIT|U[1-4])(?::(\d{1,2}))?\}/g;
const LITERAL = /^[A-Z0-9 ./_-]*$/;
const PREFIX = /^[A-Z0-9]{2,6}$/;
const UNIT_WIDTH = 8;
// Brace text goes in as values: a bare { is ICU syntax inside a Lingui message.
const SEQ = "{SEQ}";
const SEQ_N = "{SEQ:n}";
const MEMBER = "{MEMBER}";
const PREFIX_TOKEN = "{PREFIX}";

/** Tokens a member scheme may use; staff schemes drop the member and unit ones. */
export const MEMBER_TOKENS = ["{PREFIX}", "{SEQ:4}", "{MEMBER:4}", "{YYYY}", "{YY}", "{UNIT}", "{U1}", "{U2}", "{U3}", "{U4}"] as const;
export const STAFF_TOKENS = ["{PREFIX}", "{SEQ:4}", "{YYYY}", "{YY}"] as const;

export type PatternProblem = { field: "prefix" | "pattern"; message: string };

/** Fills every token the way the server does; `year` is the sample year. */
export function renderPattern(pattern: string, prefix: string, seq: number, year = new Date().getFullYear()) {
  return pattern.replace(TOKEN, (_all, name: string, width?: string) => {
    const pad = (value: number) => String(value).padStart(Number(width ?? 1), "0");
    if (name === "PREFIX") return prefix;
    if (name === "SEQ") return pad(seq);
    if (name === "MEMBER") return pad(seq);
    if (name === "YYYY") return String(year).padStart(4, "0");
    if (name === "YY") return String(year % 100).padStart(2, "0");
    return "NA".slice(0, UNIT_WIDTH);
  });
}

/** The first rule a draft breaks, or null. An empty pattern means "no scheme" and is fine. */
export function patternProblem(prefixText: string, patternText: string, allowed: readonly string[] = MEMBER_TOKENS): PatternProblem | null {
  const prefix = prefixText.trim().toUpperCase();
  const pattern = patternText.trim().toUpperCase();
  if (prefix && !PREFIX.test(prefix)) return { field: "prefix", message: t`Use 2 to 6 capital letters or digits.` };
  if (!pattern) return null;
  const tokens = [...pattern.matchAll(TOKEN)];
  const known = new Set(allowed.map((token) => token.replace(/[{}]/g, "").split(":")[0]));
  if (tokens.some((match) => !known.has(match[1]))) return { field: "pattern", message: t`That token is not available here.` };
  if (tokens.filter((match) => match[1] === "SEQ").length !== 1) return { field: "pattern", message: t`Use ${SEQ} or ${SEQ_N} exactly once.` };
  if (tokens.some((match) => match[2] && match[1] !== "SEQ" && match[1] !== "MEMBER")) {
    return { field: "pattern", message: t`Only ${SEQ} and ${MEMBER} take a width.` };
  }
  if (tokens.some((match) => match[1] === "PREFIX") && !prefix) return { field: "prefix", message: t`Add a prefix, or remove ${PREFIX_TOKEN} from the pattern.` };
  if (!LITERAL.test(pattern.replace(TOKEN, ""))) {
    return { field: "pattern", message: t`Use capital letters, digits, spaces and . / _ - around the tokens.` };
  }
  const longest = pattern.replace(TOKEN, (_all, name: string, width?: string) => {
    if (name === "PREFIX") return prefix;
    if (name === "SEQ" || name === "MEMBER") return "9".repeat(Math.max(6, Number(width ?? 1)));
    if (name === "YYYY") return "2099";
    if (name === "YY") return "99";
    return "X".repeat(UNIT_WIDTH);
  });
  if (longest.length > MAX_NUMBER_LENGTH) return { field: "pattern", message: t`A number can be at most ${MAX_NUMBER_LENGTH} characters long.` };
  return null;
}

/** Three sample numbers of a draft, for the live preview. */
export function samplesOf(prefix: string, pattern: string) {
  const clean = pattern.trim().toUpperCase();
  return clean ? [1, 2, 3].map((seq) => renderPattern(clean, prefix.trim().toUpperCase(), seq)) : [];
}

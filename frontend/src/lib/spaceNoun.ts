import { t } from "@lingui/core/macro";

/**
 * Decision 295: a space is a makerspace or an organization workspace. The kind changes
 * wording and defaults only, never what a screen can do. The server sends `space_noun`
 * (`makerspace` | `organization`) as a wording key; the noun itself is translated here and
 * dropped into sentences through a `${noun}` placeholder.
 */
export type SpaceKind = "makerspace" | "organization";

type KindCarrier = { kind?: string | null; space_noun?: string | null } | null | undefined;

/** Anything other than an explicit organization is a makerspace (absent = makerspace). */
export function spaceKindOf(space: KindCarrier): SpaceKind {
  return (space?.space_noun ?? space?.kind) === "organization" ? "organization" : "makerspace";
}

/** The lowercase noun for mid-sentence use: "makerspace" / "organization". */
export function spaceNoun(kind: SpaceKind): string {
  return kind === "organization" ? t`organization` : t`makerspace`;
}

/** The capitalised noun for titles and labels: "Makerspace" / "Organization". */
export function spaceNounTitle(kind: SpaceKind): string {
  return kind === "organization" ? t`Organization` : t`Makerspace`;
}

/** Shorthand for a space-like row: `nounOf(space)` / `nounTitleOf(space)`. */
export const nounOf = (space: KindCarrier) => spaceNoun(spaceKindOf(space));
export const nounTitleOf = (space: KindCarrier) => spaceNounTitle(spaceKindOf(space));

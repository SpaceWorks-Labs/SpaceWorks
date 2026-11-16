import type { Phase } from "./fetch.census-D12";
import type { RouteCase } from "./source.census-D12";
import { retryDefect } from "./retryDefects.census-D12";
import { stateDefect } from "./stateDefects.census-D12";
import { contextlessExemption } from "./contextless.census-D12";

// Every exception is explicit, scoped to a screen/state and reviewable. No fallback exemptions.
// Static pages still participate in render/theme/i18n cases. Their configuration queries do not
// turn the static article/catalogue itself into an empty or permission-controlled collection.
export const EXEMPTIONS: Record<string, Partial<Record<Phase, string>>> = {
  AboutLandingGate: {
    loading: "LandingGate.tsx:20 uses configuration only for admission to the bundled product landing; optional landing counters do not gate it (decisions 300/424).",
    empty: "The bundled product landing is an article, not a tenant collection (LandingGate.tsx:24).",
    error: "Optional public landing counters can fail without replacing the bundled article (LandingGate.tsx:24).",
    permission: "The product landing is public; tenant authority belongs to linked screens (LandingGate.tsx:24).",
    module: "The product article explains the service independently of tenant modules (LandingGate.tsx:24).",
  },
  LandingGate: {
    empty: "Decisions 300/424: an empty central directory intentionally selects the bundled landing article (LandingGate.tsx:14), not a directory empty notice.",
    error: "Decisions 300/424: with the landing on, a failed directory read (spaces.isError, LandingGate.tsx:14) selects the bundled article, which has no directory to retry.",
    permission: "Decisions 300/424: any directory refusal selects the public bundled article (LandingGate.tsx:14); no tenant authority is requested.",
    module: "Decisions 300/424: a refused directory selects the bundled article (LandingGate.tsx:14); the directory's own module state is shown on /spaces.",
  },
  FamilyHome: {
    loading: "MakerspacePage renders its hero and shortcuts from admission bootstrap; optional sections are absent while loading by design (FeaturedActivities.tsx:79-82, MakerspaceMoreSections.tsx:11).",
    empty: "The overview's content is its hero and shortcuts; sections with nothing to show are absent, never placeholder headings (FeaturedActivities.tsx:79-82, MakerspaceMoreSections.tsx:11).",
  },
  SpaceDisplayPage: {
    permission: "presence/views_display.py:114-125 is AllowAny with no authentication; a refused secret is the shared 404, so a paired TV has no permission-denied state (403 shows the transient reconnect status).",
  },
  NotFoundPage: {
    loading: "The terminal unmatched-URL screen has no resource query.",
    empty: "The terminal unmatched-URL screen is already the missing-page state.",
    error: "The unmatched-URL screen does not load a backend resource.",
    permission: "An unknown URL is public and conveys no resource authority.",
    module: "The unknown-URL fallback remains available with every optional module off.",
  },
  FeaturesPage: {
    loading: "The feature catalogue is compiled into the frontend bundle.",
    empty: "The compiled product catalogue is not a tenant collection.",
    error: "This catalogue has no remote content fetch to retry.",
    permission: "The product feature catalogue is public.",
    module: "The catalogue documents modules even when they are off.",
  },
  FeatureModulePage: {
    loading: "Module documentation is compiled into the frontend bundle.",
    empty: "A known module page is a static article; unknown module slugs use the fallback.",
    error: "The module article has no remote resource fetch to retry.",
    permission: "The module article is public product documentation.",
    module: "A module article remains readable while that module is off.",
  },
  HelpPage: {
    loading: "Help articles are bundled registry data; tenant bootstrap is admission data.",
    empty: "A help article is not a server collection; missing articles use the fallback.",
    error: "Article content is bundled, without a content-query retry.",
    permission: "Help articles explain the product publicly.",
    module: "Help remains available to explain a disabled feature.",
  },
  DocsPage: {
    loading: "Documentation uses lazy bundle imports rather than a TanStack resource query.",
    empty: "Documentation is a compiled article registry, not a tenant collection.",
    error: "Bundle-import failure is outside the requested API fetch-boundary simulation.",
    permission: "Product documentation is public.",
    module: "Product documentation is available independently of tenant modules.",
  },
  Navigate: {
    loading: "An index redirect forwards to a screen rather than loading its own resource.",
    empty: "An index redirect has no independent collection.",
    error: "An index redirect has no independent request to retry.",
    permission: "The destination screen owns admission; this index only redirects.",
    module: "The destination screen owns its module gate.",
  },
  SingleTenantHome: {
    loading: "This canonical tenant alias redirects to the tenant root without its own request.",
    empty: "The tenant root owns empty content after this alias redirects.",
    error: "The tenant root owns request retry after this alias redirects.",
    permission: "The alias only checks the configured slug and redirects.",
    module: "The destination tenant root owns module presentation.",
  },
  PrintRequestAlias: {
    loading: "Decision 340b: the legacy print URL redirects to the enumerated JobRequestPage when job intake is on; the destination owns loading.",
    empty: "Decision 340b: this alias has no collection; the canonical job-intake route owns its empty state.",
    error: "Decision 340b: the alias redirects to job intake, which owns its request errors and retries.",
    permission: "Decision 340b: the canonical job-intake route enforces permissions after this redirect.",
    module: "Decision 340b: canonical job intake owns module refusal; the old printing fallback is separately gated by machine service.",
  },
  SuperadminPage: {
    loading: "PlatformApps.tsx:5 delegates to StaffApp, whose navigation canonicalises this legacy alias; the destination owns loading (decision 572).",
    empty: "The legacy superadmin wrapper has no independent collection; the enumerated platform tab owns empty state (decision 572).",
    error: "The canonical StaffApp tab owns the request and its retry; this wrapper adds no request (decision 572).",
    permission: "The delegated StaffApp route enforces platform admission and owns refusal presentation (decision 572).",
    module: "The legacy alias delegates optional-module presentation to its canonical StaffApp destination (decision 572).",
  },
  GithubAppCallbackPage: {
    loading: "This browser app-link handoff has no API request (decision 361).",
    empty: "A consumed link disables the local handoff button; there is no remote collection.",
    error: "The operating system receives the app link; there is no fetch retry.",
    permission: "The browser handoff neither signs in nor requests authority.",
    module: "The app-link handoff remains independent of tenant modules.",
  },
  "ReauthenticationReturn:/reauth/callback": {
    loading: "The provider callback is a local popup-close page without a query.",
    empty: "The provider callback has no collection.",
    error: "The provider callback tells the person to return to the opener without fetching.",
    permission: "This callback does not grant authority; the opener verifies the challenge.",
    module: "Session reauthentication is core and has no optional module.",
  },
  "ReauthenticationReturn:/reauth/confirm": {
    module: "Authenticator email confirmation is core session security (reauthenticationApi.ts), with no optional module to switch off.",
  },
  p: {
    loading: "The programme wildcard is a terminal inline unavailable notice.",
    empty: "The programme wildcard has no independent collection.",
    error: "An unknown programme section makes no independent request.",
    permission: "The parent has already admitted the programme; this only explains an unknown section.",
    module: "The wildcard is the terminal explanation rather than an optional module surface.",
  },
};
export function exemption(row: RouteCase, phase: Phase) {
  return EXEMPTIONS[`${row.screen}:${row.pattern}`]?.[phase] ?? EXEMPTIONS[row.screen]?.[phase] ?? contextlessExemption(row, phase);
}

// Repaired defects remain named regressions; none is an expected failure.
export const REGRESSIONS = {
  "CENSUS-D12-1": { screen: "CardVerifyPage", phase: "error" as Phase,
    reason: "503 must render a distinct retryable operational error.",
    source: "features/cards/CardVerifyPage.tsx:77" },
  "CENSUS-D12-2": { screen: "CardVerifyPage", phase: "i18n",
    reason: "checkedLine must translate the sentence containing the formatted date.",
    source: "features/cards/CardVerifyPage.tsx:56" },
};
export function regressionId(row: RouteCase, phase: Phase) {
  return row.screen === REGRESSIONS["CENSUS-D12-1"].screen && phase === "error" ? "CENSUS-D12-1" : undefined;
}
export function productDefect(row: RouteCase, phase: Phase) {
  const state = stateDefect(row, phase);
  if (state) return state.id;
  // FirebaseBridgePage.tsx:50 returns only a paragraph on config.error, so no
  // browser gesture can retry the failed query (decision 573's error-with-retry).
  if (phase !== "error") return undefined;
  return retryDefect(row)?.id;
}

// An exact visible sentence from the supported UI vocabulary must accompany a typed refusal.
// The status/code assertions are independent of these presentation choices.
export const FAILURE_COPY = [
  "Census service unavailable.", "Couldn't load this page. Try again.",
  "Couldn't load this item. Try again.", "Couldn't load this space. Try again.",
  "We couldn't load the makerspaces. Please try again.", "Something went wrong.",
];
export const PERMISSION_COPY = ["Census access denied."];
export const MODULE_COPY = [
  "Census module is disabled.", "Events aren't turned on at this makerspace.",
  "Bookings aren't turned on at this makerspace.", "Machines aren't turned on at this makerspace.",
  "Public stats aren't turned on at this makerspace.", "This makerspace is not publishing inventory.",
  "Inventory is not enabled",
];
export const EMPTY_COPY = [
  "Nothing here yet.", "No upcoming events. Check back soon.", "No matching events. Try another search, filter or month.",
  "No items found.", "No products found.", "No makerspaces found.", "No public makerspaces yet.",
  "Census record not found.", "Card not found", "Item not found", "We couldn't find that page",
  "Census record not found. (not_found)", "Browser notifications are unavailable for this space.",
  "We could not find that. It may have been removed, or it belongs to a space you have not joined.",
];

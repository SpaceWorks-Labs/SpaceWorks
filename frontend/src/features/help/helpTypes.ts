/** One guide article, parsed from a content file under `src/help-content/<locale>/<section>/`. */
export type HelpArticle = {
  /** `<section>/<slug>`: the deep link is `/help/<section>/<slug>`. */
  id: string;
  section: string;
  slug: string;
  title: string;
  summary: string;
  order: number;
  keywords: string[];
  /** Extra actions that also show this article outside its section's audience. */
  actions: string[];
  /** Module keys the article needs; hidden when a known space has none of them on. */
  modules: string[];
  /** Capability keys the article needs; hidden when a known space has none of them on. */
  features: string[];
  body: string;
};

/** Who a section is written for. A reader sees it when any rule matches. */
export type HelpAudience = {
  everyone?: boolean;
  /** Any one of these staff actions, in any space. */
  actions?: string[];
  /** Event or booking grant holders (resource staff without a role). */
  grants?: ("events" | "bookings")[];
  /** The platform superadmin only. */
  platform?: boolean;
  /** A Space Manager (manage_makerspace) also sees it, to train their team. */
  spaceManager?: boolean;
};

export type HelpSection = {
  id: string;
  title: string;
  summary: string;
  audience: HelpAudience;
};

/** What the guide knows about the person reading it. Presentation only, never a security boundary. */
export type HelpReader = {
  signedIn: boolean;
  superadmin: boolean;
  actions: ReadonlySet<string>;
  eventGrants: boolean;
  bookingGrants: boolean;
};

/** The space the guide is read for, when there is one: its switches hide articles it cannot use. */
export type HelpSpace = { slug: string; modules: readonly string[]; features: readonly string[] };

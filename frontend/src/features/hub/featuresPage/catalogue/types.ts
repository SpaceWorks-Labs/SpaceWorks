import type { LucideIcon } from "lucide-react";
import type { ModuleKey } from "../../../../lib/retiredModules";

/** A real screenshot shipped under /public (none yet; the page shows the mascot until one is added). */
export type Screenshot = { src: string; alt: string; caption: string };

/**
 * What /features/<module> says about one module beyond its feature switches. Plain titles, one per line;
 * the page groups them. Keep it in step with the registries it summarises:
 *  - reports and analytics: apps/operations/report_definitions_*.py and report_coverage.py (REPORTS lane)
 *  - limits: apps/makerspaces/limit_modules.py KEY_MODULE (LIMITS lane); a module with no limit says why in `noLimits`
 *  - integrations: the channels, rails and adapters the module talks to
 * catalogue.test.ts guards completeness (every module has an entry); the wording is reviewed by hand.
 */
export type ModuleContent = {
  icon: LucideIcon;
  /** One line for the overview card. */
  value: string;
  /** Two or three plain sentences for the module page. */
  what: string;
  /** Roles that use it, as people say them. */
  roles: string[];
  /** Why the module has no limit of its own (shown instead of an empty list). */
  noLimits?: string;
  integrations: string[];
  /** What 0.12.0 added here; the page lists it and the "New in 0.12.0" strip links to it. */
  newIn?: string[];
  screenshots?: Screenshot[];
};

/** A report from the registry: its key (stable, parity-checked) and its human title. */
export type ReportRef = { key: string; title: string };

/** Hand-written content plus what the registries say: reports and analytics (registryData), limits (limitData). */
export type ModuleEntry = ModuleContent & { reports: ReportRef[]; analytics: string[]; limits: string[] };
export type Catalogue = Record<ModuleKey, ModuleEntry>;
export type CataloguePart = Partial<Record<ModuleKey, ModuleContent>>;

import type { ModulesEnum } from "../generated/api";

/**
 * Decision 340(b): retired module keys and the live key each one is read as (mirrors
 * backend apps/makerspaces/module_aliases.py RETIRED_MODULE_ALIASES). `printing` was the 3D print
 * queue; it is part of Machine service, which takes requests for every machine type. A retired key is
 * never offered in a module screen, setup or the /features pages.
 */
export const RETIRED_MODULE_ALIASES = { printing: "machine_service" } as const;
export type RetiredModule = keyof typeof RETIRED_MODULE_ALIASES;

/** The live module keys: the generated enum without retired keys (an older schema snapshot may still list them). */
export type ModuleKey = Exclude<ModulesEnum, RetiredModule>;

/** The live key a stored or linked module key means today. */
export function canonicalModuleKey(key: string): string {
  return (RETIRED_MODULE_ALIASES as Record<string, string>)[key] ?? key;
}

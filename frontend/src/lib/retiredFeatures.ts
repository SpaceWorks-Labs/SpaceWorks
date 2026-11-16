/** Decision 319: retired switches (always off on the server). Registered for drift guards, never offered in settings. */
export const RETIRED_FEATURES: ReadonlySet<string> = new Set(["machines.certifications", "machines.certification_reminders", "machines.induction_events"]);

import { t } from "@lingui/core/macro";
import type { FieldKey, SavedValue } from "./types";

/** Presentation labels only; F's server registry remains the validation authority. */
export const fields: { key: FieldKey; label: string; sensitive?: boolean; type?: "date" | "url" | "tel"; multiline?: boolean }[] = [
  { key: "name", label: t`Name` }, { key: "phone", label: t`Contact phone`, type: "tel" },
  { key: "institution", label: t`School or college` }, { key: "organization", label: t`Organisation` },
  { key: "study_level", label: t`Level of study` }, { key: "country", label: t`Country code` },
  { key: "skills", label: t`Skills (separated by commas)` }, { key: "github_url", label: t`GitHub`, type: "url" },
  { key: "linkedin_url", label: t`LinkedIn`, type: "url" }, { key: "portfolio_url", label: t`Portfolio`, type: "url" },
  { key: "shirt_size", label: t`T-shirt size` }, { key: "date_of_birth", label: t`Date of birth`, type: "date", sensitive: true },
  { key: "dietary_needs", label: t`Dietary needs`, multiline: true, sensitive: true },
  { key: "accessibility_needs", label: t`Accessibility needs`, multiline: true, sensitive: true },
  { key: "emergency_contact", label: t`Emergency contact`, sensitive: true },
];
export function textValue(value: SavedValue | null | undefined) { return Array.isArray(value) ? value.join(", ") : typeof value === "string" ? value : ""; }
export function typedValue(key: FieldKey, text: string): SavedValue { return key === "skills" ? text.split(",").map(s => s.trim()).filter(Boolean) : text; }

import type { FieldKey, SavedValue } from "./types";

/** Presentation labels only; F's server registry remains the validation authority. */
export const fields: { key: FieldKey; label: string; sensitive?: boolean; type?: "date" | "url" | "tel"; multiline?: boolean }[] = [
  { key: "name", label: "Name" }, { key: "phone", label: "Contact phone", type: "tel" },
  { key: "institution", label: "School or college" }, { key: "organization", label: "Organisation" },
  { key: "study_level", label: "Level of study" }, { key: "country", label: "Country code" },
  { key: "skills", label: "Skills (separated by commas)" }, { key: "github_url", label: "GitHub", type: "url" },
  { key: "linkedin_url", label: "LinkedIn", type: "url" }, { key: "portfolio_url", label: "Portfolio", type: "url" },
  { key: "shirt_size", label: "T-shirt size" }, { key: "date_of_birth", label: "Date of birth", type: "date", sensitive: true },
  { key: "dietary_needs", label: "Dietary needs", multiline: true, sensitive: true },
  { key: "accessibility_needs", label: "Accessibility needs", multiline: true, sensitive: true },
  { key: "emergency_contact", label: "Emergency contact", sensitive: true },
];
export function textValue(value: SavedValue | null | undefined) { return Array.isArray(value) ? value.join(", ") : typeof value === "string" ? value : ""; }
export function typedValue(key: FieldKey, text: string): SavedValue { return key === "skills" ? text.split(",").map(s => s.trim()).filter(Boolean) : text; }

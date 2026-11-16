import { t } from "@lingui/core/macro";
import type { TemplateChoice } from "./types";

/** Mirrors the closed v1 routing field catalogue; server configuration selects tuples. */
const fields: Record<string, readonly string[]> = {
  in_bank: ["holder_name", "account_number", "ifsc", "bank_name"], in_upi: ["holder_name", "upi_id"],
  us_bank: ["holder_name", "routing_number", "account_number", "account_type"],
  iban_bank: ["holder_name", "iban", "swift", "bank_name"],
  au_bank: ["holder_name", "bank_name", "account_number", "bsb", "swift"],
  ca_bank: ["holder_name", "bank_name", "account_number", "institution_number", "transit_number", "swift"],
  nz_bank: ["holder_name", "bank_name", "account_number", "bank_code", "branch_code", "swift"],
  email: ["holder_name", "payout_email"], cash: ["holder_name"], cheque: ["holder_name", "delivery_instructions"], other: ["holder_name"],
};
const ibanCountries = ["AT", "BE", "CH", "DE", "DK", "ES", "FI", "FR", "GB", "IE", "IT", "NL", "NO", "PL", "PT", "SE"];
export function templateFields(choice: TemplateChoice): readonly string[] | null {
  const [country, method, key, version] = choice;
  if (version !== 1 || !["IN", "US", "AU", "CA", "NZ", ...ibanCountries].includes(country)) return null;
  const expected = ["cash", "cheque", "other"].includes(method) ? method : ["paypal", "wise"].includes(method) ? "email"
    : country === "IN" && method === "upi" ? "in_upi" : method === "bank_transfer"
      ? ibanCountries.includes(country) ? "iban_bank" : `${country.toLowerCase()}_bank` : null;
  return key === expected ? fields[key] ?? null : null;
}
export const fieldLabel = (key: string) => ({ holder_name: t`Account holder name`, ifsc: t`IFSC`, upi_id: t`UPI ID`, swift: t`SWIFT / BIC`,
  iban: t`IBAN`, bsb: t`BSB`, payout_email: t`Payout email` } as Record<string, string>)[key] ?? key.replace(/_/g, " ").replace(/^./, value => value.toUpperCase());

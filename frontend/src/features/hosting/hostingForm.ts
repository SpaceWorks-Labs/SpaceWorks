import { StructuredApiError } from "../../lib/api/errors";
import type * as Api from "../../generated/api";
import type { HostingRequestBody } from "./hostingApi";

/** Every field as the text the input holds; `expected_members` is converted to a number on submit. */
export type HostingFormValue = Required<Api.HostingRequestSubmit> & { expected_members: string };
export type HostingFormKey = keyof HostingFormValue;

export const EMPTY_HOSTING_FORM: HostingFormValue = {
  applicant_name: "", applicant_email: "", applicant_phone: "", space_name: "", location: "",
  space_website_url: "", description: "", proposed_slug: "", new_organization_name: "", website: "", expected_members: "",
};

export const HOSTING_ACK = "Check your email to confirm your request.";

const OPTIONAL: HostingFormKey[] = ["applicant_phone", "space_website_url", "proposed_slug", "new_organization_name"];

/** Trimmed request body. Blank optional fields are left out; the honeypot is always sent untouched. */
export function hostingRequestBody(form: HostingFormValue, { includeOrganization = true } = {}): HostingRequestBody {
  const body: HostingRequestBody = {
    applicant_name: form.applicant_name.trim(),
    applicant_email: form.applicant_email.trim(),
    space_name: form.space_name.trim(),
    location: form.location.trim(),
    description: form.description.trim(),
    website: form.website,
  };
  for (const key of OPTIONAL) {
    if (key === "new_organization_name" && !includeOrganization) continue;
    const value = form[key].trim();
    if (value) body[key as Exclude<HostingFormKey, "website" | "expected_members">] = value;
  }
  const members = Number(form.expected_members.trim());
  if (form.expected_members.trim() && Number.isInteger(members) && members > 0) body.expected_members = members;
  return body;
}

/** DRF field errors (`{field: ["message"]}`) as one message per field. */
export function hostingFieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof StructuredApiError) || error.status !== 400) return {};
  const errors: Record<string, string> = {};
  for (const [key, value] of Object.entries(error.body)) {
    const first = Array.isArray(value) ? value.find((item) => typeof item === "string") : value;
    if (typeof first === "string" && key !== "detail" && key !== "code") errors[key] = first;
  }
  return errors;
}

/** The form-level message: field errors are shown inline, so this only summarises them. */
export function hostingErrorText(error: unknown, notFound: string) {
  if (error instanceof StructuredApiError) {
    if (error.status === 429) return "Too many requests from this connection. Please try again later.";
    if (error.status === 404) return notFound;
    if (error.status === 400) {
      const errors = hostingFieldErrors(error);
      return errors.non_field_errors ?? error.detail ?? "Check the highlighted fields and try again.";
    }
    return error.message;
  }
  return error instanceof Error ? error.message : "Could not send your request.";
}

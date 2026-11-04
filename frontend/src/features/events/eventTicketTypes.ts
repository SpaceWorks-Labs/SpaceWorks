import type { PublicEvent } from "../../generated/api";
import type { CustomFormSchema } from "../forms/customFormTypes";

// These inline JSON schemas are coarse in OpenAPI; the form/ticket components need validated domain fields.
export type EventTicket = {
  id: number; name: string; amount: string; audience: "member" | "public";
  spots_left: number | null;
};
type CoreFields = "public_token" | "title" | "description" | "starts_at" | "ends_at" | "location"
  | "payment_amount" | "currency" | "availability" | "registration_requires_approval"
  | "effective_registration_cutoff_at" | "registration_open" | "image_url" | "status" | "series";
type OptionalFields = "website" | "audience_label" | "participating_organizations" | "show_registration_count"
  | "registration_count" | "registration_audience" | "ticket_selection_required" | "promo_codes_enabled" | "tags";
export type PublicEventDetail = Pick<PublicEvent, CoreFields> & Partial<Pick<PublicEvent, OptionalFields>> & {
  capacity: number | null;
  ticket_types?: EventTicket[];
  category?: { id: number; name: string; slug: string } | null;
  custom_form: CustomFormSchema;
};

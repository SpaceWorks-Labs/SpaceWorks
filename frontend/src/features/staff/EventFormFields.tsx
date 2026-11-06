import { t } from "@lingui/core/macro";
import type { ReactNode } from "react";
import type { EventPayload, StaffEvent } from "./eventsApi";
import { EventEssentialFields, EventMoreFields } from "./EventFieldGroups";

export type EventFormValues = Omit<EventPayload, "starts_at" | "ends_at" | "registration_cutoff_at"> & {
  starts_at: string;
  ends_at: string;
  registration_cutoff_at: string | null;
};

export const emptyEventForm: EventFormValues = {
  accent_preset: "", title: "", description: "", starts_at: "", ends_at: "", location: "",
  timezone_name: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
  capacity: 0, payment_amount: "0.00", registration_requires_approval: false,
  registration_cutoff_at: null, registration_cutoff_lead_minutes: null,
  cancellation_cutoff_hours: null,
  show_registration_count: true,
  is_public: false, registration_audience: "members", category_id: null, tags: [],
  custom_form: null, listing: "listed", delivery_mode: "in_person",
};

function localDate(value: string) {
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}

export function valuesFor(event: StaffEvent): EventFormValues {
  return {
    accent_preset: event.accent_preset ?? "", title: event.title, description: event.description,
    starts_at: localDate(event.starts_at), ends_at: localDate(event.ends_at),
    timezone_name: event.timezone_name,
    location: event.location, capacity: event.capacity,
    payment_amount: event.payment_amount,
    registration_requires_approval: event.registration_requires_approval,
    registration_cutoff_at: event.registration_cutoff_at ? localDate(event.registration_cutoff_at) : null,
    registration_cutoff_lead_minutes: event.registration_cutoff_lead_minutes,
    cancellation_cutoff_hours: event.cancellation_cutoff_hours ?? null,
    show_registration_count: event.show_registration_count ?? true,
    is_public: event.is_public, registration_audience: event.registration_audience ?? "members", category_id: event.category_id ?? null, tags: event.tags ?? [],
    custom_form: event.custom_form,
    listing: event.listing ?? "listed", delivery_mode: event.delivery_mode ?? "in_person",
    // Only an editor of a space with online events reads the link; otherwise it is never resent.
    ...(event.join_url ? { join_url: event.join_url } : {}),
  };
}

export function payloadFor(values: EventFormValues): EventPayload {
  return {
    ...values, tags: (values.tags ?? []).map((tag) => tag.trim()).filter(Boolean), title: values.title.trim(), description: values.description.trim(),
    location: values.location.trim(), starts_at: new Date(values.starts_at).toISOString(),
    ends_at: new Date(values.ends_at).toISOString(),
    registration_cutoff_at: values.registration_cutoff_at ? new Date(values.registration_cutoff_at).toISOString() : null,
  };
}

export function EventFields({ values, setValues, disabled = false, approvalLocked = false, settings = false, canEditDetails = true, canEditSchedule = true, canEditPrice = true, organizationAudienceEnabled = false, onlineEnabled = false, layout = "all", moreExtras }: {
  values: EventFormValues; setValues: (values: EventFormValues) => void;
  disabled?: boolean; approvalLocked?: boolean; settings?: boolean;
  canEditDetails?: boolean; canEditSchedule?: boolean; canEditPrice?: boolean; organizationAudienceEnabled?: boolean;
  /** The events.online_delivery switch is on: show how people attend and the join link. */
  onlineEnabled?: boolean;
  /** "split" tucks everything past the essentials into a collapsed "More options"; "essentials" omits it. */
  layout?: "all" | "split" | "essentials";
  /** Extra create-time steps (partners, organizers) that belong behind "More options". */
  moreExtras?: ReactNode;
}) {
  // Event staff grants split editing three ways: details, schedule (publish) and price (manager).
  const group = { values, setValues, settings, organizationAudienceEnabled, onlineEnabled, approvalLocked,
    details: disabled || !canEditDetails, schedule: disabled || !canEditSchedule, price: disabled || !canEditPrice };
  const grid = settings ? "divide-y divide-line" : "grid gap-4 sm:grid-cols-2";
  if (layout === "essentials") return <div className={grid}><EventEssentialFields {...group} /></div>;
  if (layout === "all") return <div className={grid}><EventEssentialFields {...group} /><EventMoreFields {...group} /></div>;
  return <div className="grid gap-4">
    <div className={grid}><EventEssentialFields {...group} /></div>
    {moreExtras && values.registration_audience === "participating_organizations" ? <p role="note" className="text-sm text-muted">{t`Choose the participating organizations under More options.`}</p> : null}
    {/* A required control inside a closed disclosure cannot take focus, so a failed submit opens it. */}
    <details className="rounded-xl border border-line bg-panel" onInvalidCapture={(event) => { event.currentTarget.open = true; }}>
      <summary className="flex min-h-11 cursor-pointer items-center px-4 py-3 text-sm font-semibold text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">{t`More options`}</summary>
      <div className="grid gap-4 border-t border-line p-4">
        <p className="text-sm text-muted">{t`Description, price, cutoffs, approval, the registration form and partners. Every option can be changed later in the event's settings.`}</p>
        <div className={grid}><EventMoreFields {...group} /></div>
        {moreExtras}
      </div>
    </details>
  </div>;
}

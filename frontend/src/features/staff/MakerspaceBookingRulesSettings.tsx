import { t } from "@lingui/core/macro";
import { SettingsQueryState } from "./SettingsQueryState";
import { ErrorBlock, Pagination } from "../../components/ui";
import { SettingsEditorActions } from "./SettingsEditorActions";
import { SettingsRow } from "../../components/ui";
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { StructuredApiError, staffRequest } from "../../lib/api";
import { useStaffGet } from "./StaffPanels";
import type { Makerspace } from "./panels/shared";
import { bookingKeys } from "./bookingsApi";
import type { Paginated } from "./eventsApiTypes";
import { LogoLoader } from "../../components/LogoLoader";

type SpaceRules = {
  id: number;
  name: string;
  is_active: boolean;
  approval_mode: "instant" | "approve";
  min_booking_duration_minutes: number;
  max_booking_duration_minutes: number;
  booking_lead_time_minutes: number;
  max_booking_advance_days: number;
  buffer_before_minutes: number;
  buffer_after_minutes: number;
  cancellation_cutoff_hours: number;
};

type RuleField =
  | "min_booking_duration_minutes"
  | "max_booking_duration_minutes"
  | "booking_lead_time_minutes"
  | "max_booking_advance_days"
  | "buffer_before_minutes"
  | "buffer_after_minutes"
  | "cancellation_cutoff_hours"
  | "approval_mode";
type NumberRuleField = Exclude<RuleField, "approval_mode">;
type RuleDraft = Record<NumberRuleField, string> & {
  approval_mode: SpaceRules["approval_mode"];
};
type FieldErrors = Partial<Record<RuleField, string>>;

const NUMBER_FIELDS: Array<{ key: NumberRuleField; label: string; min: number }> = [
  { key: "min_booking_duration_minutes", label: t`Minimum booking duration (minutes)`, min: 1 },
  { key: "max_booking_duration_minutes", label: t`Maximum booking duration (minutes)`, min: 1 },
  { key: "booking_lead_time_minutes", label: t`Booking lead time (minutes)`, min: 0 },
  { key: "max_booking_advance_days", label: t`Maximum booking advance (days)`, min: 1 },
  { key: "buffer_before_minutes", label: t`Buffer before (minutes)`, min: 0 },
  { key: "buffer_after_minutes", label: t`Cleanup after (minutes)`, min: 0 },
  { key: "cancellation_cutoff_hours", label: t`Cancellation cutoff (hours before start)`, min: 0 },
];
const RULE_FIELDS: RuleField[] = [...NUMBER_FIELDS.map(({ key }) => key), "approval_mode"];

export function MakerspaceBookingRulesSettings({ makerspace }: { makerspace: Pick<Makerspace, "id"> }) {
  const [page, setPage] = useState(1);
  useEffect(() => { setPage(1); }, [makerspace.id]);
  const pageSize = 24;
  const spaces = useStaffGet<Paginated<SpaceRules>>(
    ["booking-rule-spaces", makerspace.id, page],
    `/admin/makerspaces/${makerspace.id}/spaces/?page=${page}&page_size=${pageSize}`,
  );
  const activeSpaces = spaces.data?.results.filter((space) => space.is_active) ?? [];

  return (
    <SettingsQueryState query={spaces} resource={t`booking rules`}><SettingsRow label={t`Booking rules per space`} helper={t`Buffers reserve time around each booking. A cancellation cutoff of 0 allows members to cancel any time before the booking starts.`}><div className="@container grid min-w-0 gap-4">


      {spaces.isLoading ? <LogoLoader label={t`Loading bookable spaces…`} size={48} className="min-h-16 py-3" /> : null}
      {!spaces.isLoading && activeSpaces.length === 0 ? (
        <p className="mt-3 text-sm text-muted">{t`No active bookable spaces on this page.`}</p>
      ) : null}
      {activeSpaces.length > 0 ? (
        <div className="mt-4 grid min-w-0 gap-4">
          {activeSpaces.map((space) => (
            <SpaceRuleRow key={space.id} makerspaceId={makerspace.id} space={space} />
          ))}
        </div>
      ) : null}
      {spaces.error ? <ErrorBlock error={new Error(t`Couldn't load booking rules. Try again.`)} onRetry={() => { void spaces.refetch(); }} /> : null}
      {spaces.data ? <Pagination page={page} count={spaces.data.count} pageSize={pageSize} totalPages={Math.ceil(spaces.data.count / pageSize)} onChange={setPage} disabled={spaces.isFetching} /> : null}
    </div></SettingsRow></SettingsQueryState>
  );
}

function SpaceRuleRow({ makerspaceId, space }: { makerspaceId: number; space: SpaceRules }) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<RuleDraft>(() => draftFromSpace(space));
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [rowError, setRowError] = useState("");

  useEffect(() => {
    setDraft(draftFromSpace(space));
    setFieldErrors({});
    setRowError("");
  // eslint-disable-next-line react-hooks/exhaustive-deps -- space is reseeded field by field (id and the listed rule fields); depending on the whole object would discard the draft on every refetch
  }, [
    space.id,
    space.min_booking_duration_minutes,
    space.max_booking_duration_minutes,
    space.booking_lead_time_minutes,
    space.max_booking_advance_days,
    space.buffer_before_minutes,
    space.buffer_after_minutes,
    space.cancellation_cutoff_hours,
    space.approval_mode,
  ]);

  const updateRules = useMutation({
    mutationFn: () =>
      staffRequest<SpaceRules>(`/admin/spaces/${space.id}/booking-rules/`, {
        method: "PATCH",
        body: JSON.stringify({
          min_booking_duration_minutes: Number(draft.min_booking_duration_minutes),
          max_booking_duration_minutes: Number(draft.max_booking_duration_minutes),
          booking_lead_time_minutes: Number(draft.booking_lead_time_minutes),
          max_booking_advance_days: Number(draft.max_booking_advance_days),
          buffer_before_minutes: Number(draft.buffer_before_minutes),
          buffer_after_minutes: Number(draft.buffer_after_minutes),
          cancellation_cutoff_hours: Number(draft.cancellation_cutoff_hours),
          approval_mode: draft.approval_mode,
        }),
      }),
    onMutate: () => {
      setFieldErrors({});
      setRowError("");
    },
    onError: (error) => {
      const parsed = parseRuleErrors(error);
      setFieldErrors(parsed.fieldErrors);
      setRowError(parsed.rowError);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["booking-rule-spaces", makerspaceId] });
      queryClient.invalidateQueries({ queryKey: bookingKeys.spaces(makerspaceId) });
      queryClient.invalidateQueries({ queryKey: bookingKeys.detail(space.id) });
    },
  });

  return (
    <form
      className="grid min-w-0 gap-3 rounded-md border border-line p-4"
      onSubmit={(event) => {
        event.preventDefault();
        updateRules.mutate();
      }}
    >
      <h4 className="text-sm font-semibold text-ink">{space.name}</h4>
      <div className="grid min-w-0 gap-3 @md:grid-cols-2">
        {NUMBER_FIELDS.map(({ key, label, min }) => (
          <label className="grid min-w-0 content-start gap-1 text-sm text-ink" key={key}>
            <span className="font-semibold">{label}</span>
            <input
              aria-label={`${label} for ${space.name}`}
              className="desk-input"
              type="number"
              min={min}
              value={draft[key]}
              disabled={updateRules.isPending}
              onChange={(event) => setDraft((current) => ({ ...current, [key]: event.target.value }))}
            />
            {fieldErrors[key] ? <span className="text-xs text-danger">{fieldErrors[key]}</span> : null}
          </label>
        ))}
        <label className="grid min-w-0 content-start gap-1 text-sm text-ink">
          <span className="font-semibold">{t`Approval mode`}</span>
          <select
            aria-label={t`Approval mode for ${space.name}`}
            className="desk-input"
            value={draft.approval_mode}
            disabled={updateRules.isPending}
            onChange={(event) => setDraft((current) => ({
              ...current,
              approval_mode: event.target.value as SpaceRules["approval_mode"],
            }))}
          >
            <option value="instant">{t`Instant confirmation`}</option>
            <option value="approve">{t`Staff approval required`}</option>
          </select>
          {fieldErrors.approval_mode ? (
            <span className="text-xs text-danger">{fieldErrors.approval_mode}</span>
          ) : null}
        </label>
      </div>
      <div>
        <SettingsEditorActions dirty={JSON.stringify(draft) !== JSON.stringify(draftFromSpace(space))} onDiscard={() => { setDraft(draftFromSpace(space)); setFieldErrors({}); setRowError(""); }} pending={updateRules.isPending} disabled={updateRules.isPending} />
      </div>
      {rowError ? <p className="text-sm text-danger">{rowError}</p> : null}
    </form>
  );
}

function draftFromSpace(space: SpaceRules): RuleDraft {
  return {
    min_booking_duration_minutes: String(space.min_booking_duration_minutes),
    max_booking_duration_minutes: String(space.max_booking_duration_minutes),
    booking_lead_time_minutes: String(space.booking_lead_time_minutes),
    max_booking_advance_days: String(space.max_booking_advance_days),
    buffer_before_minutes: String(space.buffer_before_minutes),
    buffer_after_minutes: String(space.buffer_after_minutes),
    cancellation_cutoff_hours: String(space.cancellation_cutoff_hours),
    approval_mode: space.approval_mode,
  };
}

function parseRuleErrors(error: unknown): { fieldErrors: FieldErrors; rowError: string } {
  if (!(error instanceof StructuredApiError) || error.status !== 400) {
    return {
      fieldErrors: {},
      rowError: error instanceof Error ? error.message : "Unable to save booking rules.",
    };
  }

  const fieldErrors: FieldErrors = {};
  RULE_FIELDS.forEach((field) => {
    const message = errorMessage(error.body[field]);
    if (message) fieldErrors[field] = message;
  });
  const rowError = [errorMessage(error.body.detail), errorMessage(error.body.non_field_errors)]
    .filter(Boolean)
    .join(" ");

  return {
    fieldErrors,
    rowError: rowError || (Object.keys(fieldErrors).length === 0 ? error.message : ""),
  };
}

function errorMessage(value: unknown) {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.filter((item) => typeof item === "string").join(" ");
  return "";
}

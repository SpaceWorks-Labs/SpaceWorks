import { t } from "@lingui/core/macro";

const humanize = (value: string) => value.replace(/_/g, " ");

/** Translated wording for an `EventStageForm.stage` value. */
export function stageNameLabel(stage: string): string {
  switch (stage) {
    case "application": return t`Application`;
    case "shortlisted": return t`Shortlisted`;
    case "accepted_rsvp": return t`Accepted and RSVP`;
    case "pre_event": return t`Before the event`;
    case "post_event": return t`After the event`;
    default: return humanize(stage);
  }
}

/** Translated wording for an `EventStageForm.state` value. */
export function stageDefinitionStateLabel(state: string): string {
  switch (state) {
    case "draft": return t`Draft`;
    case "published": return t`Published`;
    case "retired": return t`Retired`;
    default: return humanize(state);
  }
}

/** Translated wording for a stage assignment's due state. */
export function stageAssignmentStateLabel(state: string): string {
  switch (state) {
    case "scheduled": return t`Scheduled`;
    case "open": return t`Open`;
    case "completed": return t`Completed`;
    case "overdue": return t`Overdue`;
    case "cancelled": return t`Cancelled`;
    default: return humanize(state);
  }
}

/** Translated wording for an action a missed stage form can block. */
export function stageBlockedActionLabel(action: string): string {
  switch (action) {
    case "rsvp": return t`RSVP`;
    case "check_in": return t`Check-in`;
    case "claim_submit": return t`Submitting a claim`;
    default: return humanize(action);
  }
}

/** Translated wording for a stage form opening or deadline schedule mode. */
export function stageScheduleModeLabel(mode: string): string {
  switch (mode) {
    case "trigger": return t`When the stage starts`;
    case "absolute": return t`At a set date and time`;
    case "after_trigger": return t`A set time after the stage starts`;
    case "event_start": return t`Relative to the event start`;
    case "event_end": return t`Relative to the event end`;
    default: return humanize(mode);
  }
}

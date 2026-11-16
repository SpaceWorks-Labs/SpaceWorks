import { t } from "@lingui/core/macro";

import { StatusPill } from "../../../components/ui";

/** An item lendable only within an event context (decision 221b). */
export function EventsOnlyBadge() {
  return <StatusPill tone="info" icon="Calendar" label={t`Events only`} />;
}

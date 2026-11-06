import { t } from "@lingui/core/macro";
import { PassState } from "../../components/delight/PassState";
import { ConfirmationGreeting } from "../../components/delight/StatusDetails";

/** G maps the existing booking response; only persisted checked_in_at tears the stub. */
export function BookingPass({ name, title, checkedInAt }: { name: string; title: string; checkedInAt: string | null }) {
  return <PassState title={title} value={checkedInAt ? { state: "completed", label: t`Checked in`, completedAt: checkedInAt } : { state: "ready", label: t`Ready for check-in` }}>
    <ConfirmationGreeting name={name} />
  </PassState>;
}

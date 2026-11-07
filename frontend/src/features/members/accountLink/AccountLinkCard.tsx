import { t } from "@lingui/core/macro";
import { useId, useState } from "react";
import { Link2 } from "lucide-react";
import { Card } from "../../../components/ui";
import { AccountLinkFlow } from "./AccountLinkFlow";

/** Entry point on the account page. `suggested` comes from the auth payload's `merge_suggested`. */
export function AccountLinkCard({ suggested = false }: { suggested?: boolean }) {
  const [open, setOpen] = useState(false);
  const titleId = useId();
  return <Card className={suggested ? "border-accent" : ""}>
    <section aria-labelledby={titleId} className="flex flex-wrap items-start gap-4">
      <Link2 aria-hidden="true" size={24} className="mt-0.5 shrink-0 text-accent-ink" />
      <div className="grid min-w-0 flex-1 basis-64 gap-2">
        <h3 id={titleId} className="title-section">{suggested ? t`We found another account that may be yours.` : t`Link another account`}</h3>
        <p className="text-sm text-muted">{t`Do you have a second account (for example a staff account from before)? Link it so your roles and history live in one account.`}</p>
      </div>
      <button type="button" className={`${suggested ? "desk-button-primary" : "desk-button"} min-h-11`}
        onClick={() => setOpen(true)}>{t`Link an account`}</button>
    </section>
    {/* Unmounted when closed, so a cancelled attempt never leaks its fields into the next one. */}
    {open ? <AccountLinkFlow open onClose={() => setOpen(false)} /> : null}
  </Card>;
}

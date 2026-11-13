import { t } from "@lingui/core/macro";
import { Modal } from "../../../components/ui";
import type { AccountProfile } from "../accountProfileTypes";
import { asVisitor, GlobalProfileView } from "../view/GlobalProfileView";

/** The saved profile as another signed-in member would see it: switched-off sections are dropped. */
export function ProfilePreviewDialog({ open, onClose, profile }: { open: boolean; onClose: () => void; profile: AccountProfile }) {
  return <Modal open={open} onClose={onClose} size="xl" title={t`Preview: what other members see`}>
    <p className="mb-6 rounded-control bg-info-soft p-3 text-sm text-info-ink">
      {t`Built from your saved profile. Save any edits first. Logged-out visitors see the same sections only if you turned on the open web.`}</p>
    {open ? <GlobalProfileView profile={asVisitor(profile)} preview /> : null}
  </Modal>;
}

import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { Modal } from "../../../components/ui";
import { BoxArt } from "../../../components/BoxSpinner";

/**
 * Showing the profile on the open web is a fresh, explicit consent every time: the box starts unticked on every
 * open, and the request carries `publication_consent: true` only when it is ticked. The server refuses the switch
 * without it, so this is the visible half of an enforced rule.
 */
export function PublishConsentDialog({ open, handle, pending, error, onCancel, onPublish }: {
  open: boolean; handle: string; pending: boolean; error?: string; onCancel: () => void; onPublish: () => void;
}) {
  const [agreed, setAgreed] = useState(false);
  useEffect(() => { if (!open) setAgreed(false); }, [open]);
  const close = () => { setAgreed(false); onCancel(); };
  return <Modal open={open} onClose={close} title={t`Show your profile on the open web?`} footer={
    <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
      <button type="button" className="desk-button w-full sm:w-auto" disabled={pending} onClick={close}>{t`Cancel`}</button>
      <button type="button" className="desk-button-primary w-full sm:w-auto" disabled={!agreed || pending}
        onClick={() => { onPublish(); }}>{pending ? <><BoxArt size={16} mono />{t`Saving…`}</> : t`Show on the open web`}</button>
    </div>}>
    <div className="grid gap-4 text-sm text-ink">
      <p>{t`Anyone on the internet, signed in or not, will be able to open `}<span className="font-semibold">/{handle}</span>{t`, and search engines may list it and show a preview card.`}</p>
      <ul className="list-disc space-y-1 pl-5 text-muted">
        <li>{t`Shown: the sections you have switched on, such as your name, avatar, headline, bio, spaces, experience, achievements and public projects.`}</li>
        <li>{t`Sections you switched off stay hidden, here and for everyone else.`}</li>
        <li>{t`Never shown: your email address or phone number.`}</li>
        <li>{t`You can turn this off at any time; the open-web page goes offline straight away.`}</li>
      </ul>
      <label className="flex min-h-11 items-start gap-3">
        <input type="checkbox" className="mt-0.5 h-5 w-5 accent-accent" checked={agreed} onChange={event => setAgreed(event.target.checked)} />
        <span>{t`I understand my profile will be visible to logged-out visitors and search engines, and I consent.`}</span>
      </label>
      {error ? <p role="alert" className="text-danger">{error}</p> : null}
    </div>
  </Modal>;
}

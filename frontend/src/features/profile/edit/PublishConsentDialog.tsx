import { useEffect, useState } from "react";
import { Modal } from "../../../components/ui";

/**
 * Publishing is a fresh, explicit act every time: the box starts unticked on every open, and
 * the request carries `publication_consent: true` only when it is ticked. The server refuses
 * a publish without it, so this is the visible half of an enforced rule.
 */
export function PublishConsentDialog({ open, handle, pending, error, onCancel, onPublish }: {
  open: boolean; handle: string; pending: boolean; error?: string; onCancel: () => void; onPublish: () => void;
}) {
  const [agreed, setAgreed] = useState(false);
  useEffect(() => { if (!open) setAgreed(false); }, [open]);
  const close = () => { setAgreed(false); onCancel(); };
  return <Modal open={open} onClose={close} title="Publish your public profile?" footer={
    <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
      <button type="button" className="desk-button w-full sm:w-auto" disabled={pending} onClick={close}>Cancel</button>
      <button type="button" className="desk-button-primary w-full sm:w-auto" disabled={!agreed || pending}
        onClick={() => { onPublish(); }}>{pending ? "Publishing…" : "Publish profile"}</button>
    </div>}>
    <div className="grid gap-4 text-sm text-ink">
      <p>Anyone on the internet will be able to open <span className="font-semibold">/{handle}</span>, and search engines may list it.</p>
      <ul className="list-disc space-y-1 pl-5 text-muted">
        <li>Shown: your name, avatar, headline, institution, bio, domains, skills, links, timeline and public projects.</li>
        <li>Activity, events and other sections stay hidden until you switch each one on.</li>
        <li>Never shown: your email address or phone number.</li>
        <li>You can unpublish at any time; the page goes offline straight away.</li>
      </ul>
      <label className="flex min-h-11 items-start gap-3">
        <input type="checkbox" className="mt-0.5 h-5 w-5 accent-accent" checked={agreed} onChange={event => setAgreed(event.target.checked)} />
        <span>I understand this page is public and I agree to publish it.</span>
      </label>
      {error ? <p role="alert" className="text-danger">{error}</p> : null}
    </div>
  </Modal>;
}

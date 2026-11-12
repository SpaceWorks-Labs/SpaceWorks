import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Field, SettingsRow, StatusPill } from "../../components/ui";
import { StructuredApiError, staffRequest } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import { BoxArt } from "../../components/BoxSpinner";

/** Parity E-B8 (A19) fields on the makerspace payload; typed locally until `generated/api.ts` is regenerated. */
type SenderSettings = { email_from_name?: string; email_reply_to?: string; smtp_verified?: boolean;
  smtp_verified_at?: string | null; enabled_features?: string[] };
type TestResult = { accepted: boolean; code: string; smtp_verified: boolean; smtp_verified_at: string | null };

export function testResultMessage(code: string) {
  switch (code) {
    case "provider_accepted": return t`Test email accepted. Check your inbox; this space now sends through its own server.`;
    case "smtp_not_configured": return t`Save this space's own SMTP server first, then send the test.`;
    case "smtp_probe_failed": return t`The server could not be reached or refused the sign-in. Check the host, port, security and password.`;
    case "smtp_probe_not_accepted": return t`The server answered but did not accept the message. Check the sender address is allowed on that account.`;
    case "no_account_email": return t`Your own account has no email address, so there is nowhere to send the test.`;
    default: return t`The test did not complete. Try again.`;
  }
}

/**
 * Sender name and Reply-To (switch `email.sender_identity`), and the test a space's own SMTP account must pass
 * before mail goes through it. The test message goes to the signed-in staff member's own address only.
 */
export function SpaceEmailSender({ makerspaceId }: { makerspaceId: number }) {
  const client = useQueryClient();
  const path = `/admin/makerspaces/${makerspaceId}`;
  const key = ["makerspace-settings", makerspaceId];
  const space = useQuery({ queryKey: key, queryFn: () => staffRequest<SenderSettings>(path) });
  const identityOn = space.data?.enabled_features?.includes("email.sender_identity") ?? false;
  const [name, setName] = useState("");
  const [replyTo, setReplyTo] = useState("");
  useEffect(() => { setName(space.data?.email_from_name ?? ""); setReplyTo(space.data?.email_reply_to ?? ""); },
    [space.data?.email_from_name, space.data?.email_reply_to]);
  const save = useMutation({
    mutationFn: () => staffRequest<SenderSettings>(path, { method: "PATCH", body: JSON.stringify({ email_from_name: name.trim(), email_reply_to: replyTo.trim() }) }),
    onSuccess: data => { client.setQueryData(key, data); void client.invalidateQueries({ queryKey: ["staff", "makerspaces"] }); },
  });
  const test = useMutation({
    mutationFn: () => staffRequest<TestResult>(`/admin/makerspace/${makerspaceId}/email/test`, { method: "POST" }),
    onSettled: () => { void client.invalidateQueries({ queryKey: key }); },
  });
  // A 422 carries the same result body: the test ran and was refused.
  const failure = test.error instanceof StructuredApiError ? testResultMessage(String(test.error.code ?? (test.error.body as { code?: string }).code ?? ""))
    : test.error ? t`The test did not complete. Try again.` : null;
  const dirty = name !== (space.data?.email_from_name ?? "") || replyTo !== (space.data?.email_reply_to ?? "");
  const verified = space.data?.smtp_verified;
  return <>
    <SettingsRow label={t`Own mail server test`} helper={t`Mail only goes through this space's own SMTP server after a test message is accepted. Changing any SMTP setting asks for a new test.`}>
      <div className="grid min-w-0 gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill label={verified ? t`Verified` : t`Not verified`} tone={verified ? "success" : "warn"} />
          {verified && space.data?.smtp_verified_at ? <span className="text-sm text-muted">{t`Last passed ${formatDateTime(space.data.smtp_verified_at)}`}</span> : null}
        </div>
        <button type="button" className="desk-button justify-self-start" disabled={test.isPending} onClick={() => test.mutate()}>
          {test.isPending ? <><BoxArt size={16} mono />{t`Sending test…`}</> : t`Send a test email`}</button>
        <p className="text-sm text-muted">{t`The test goes to your own account's email address.`}</p>
        {test.data ? <p role="status" className="text-sm text-success-ink">{testResultMessage(test.data.code)}</p> : null}
        {failure ? <p role="alert" className="text-sm text-danger">{failure}</p> : null}
      </div>
    </SettingsRow>
    {identityOn ? <SettingsRow label={t`Sender name and reply-to`} helper={t`How this space's email appears in an inbox, and where replies go. Blank uses the plain sender address.`}>
      <form className="grid min-w-0 gap-3" onSubmit={event => { event.preventDefault(); save.mutate(); }}>
        <Field label={t`Sender name`}><input className="desk-input" maxLength={120} value={name} placeholder={t`North Lab`}
          onChange={event => { setName(event.target.value); save.reset(); }} /></Field>
        <Field label={t`Reply-to address`}><input className="desk-input" type="email" maxLength={254} value={replyTo} placeholder="hello@example.org"
          onChange={event => { setReplyTo(event.target.value); save.reset(); }} /></Field>
        {save.error ? <p role="alert" className="text-sm text-danger">{save.error.message}</p> : null}
        {save.isSuccess && !dirty ? <p role="status" className="text-sm text-muted">{t`Sender details saved.`}</p> : null}
        <button type="submit" className="desk-button-primary justify-self-start" disabled={!dirty || save.isPending}>{save.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : t`Save sender details`}</button>
      </form>
    </SettingsRow> : null}
  </>;
}

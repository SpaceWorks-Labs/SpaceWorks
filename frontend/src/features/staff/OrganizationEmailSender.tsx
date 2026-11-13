import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Field } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import { BoxArt } from "../../components/BoxSpinner";

type Sender = { sender_name: string; reply_to: string; updated_at: string | null };

/** X2 / #115a: name and Reply-To on event email when this organisation co-hosts. */
export function OrganizationEmailSender({ organizationId }: { organizationId: number }) {
  const client = useQueryClient();
  const key = ["organization-email-sender", organizationId];
  const path = `/admin/organizations/${organizationId}/email-sender/`;
  const query = useQuery({ queryKey: key, queryFn: () => staffRequest<Sender>(path), retry: false });
  const [value, setValue] = useState({ sender_name: "", reply_to: "" });
  useEffect(() => { if (query.data) setValue({ sender_name: query.data.sender_name, reply_to: query.data.reply_to }); }, [query.data]);
  const save = useMutation({ mutationFn: () => staffRequest<Sender>(path, { method: "PUT", body: JSON.stringify(value) }),
    onSuccess: data => client.setQueryData(key, data) });
  if (!query.data) return null;
  return <form className="grid gap-4" onSubmit={event => { event.preventDefault(); save.mutate(); }}>
    <p className="text-sm text-muted">{t`When you co-host an event, its email can show "your name via the space" and send replies to you. The space still sends the email from its own address, and only spaces that allow co-host senders use this.`}</p>
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label={t`Sender name`}><input className="desk-input" maxLength={80} value={value.sender_name} onChange={event => setValue({ ...value, sender_name: event.target.value })} /></Field>
      <Field label={t`Reply-to email`}><input className="desk-input" type="email" maxLength={254} value={value.reply_to} onChange={event => setValue({ ...value, reply_to: event.target.value })} /></Field>
    </div>
    {save.error ? <p role="alert" className="text-sm text-danger">{save.error instanceof Error ? save.error.message : t`Couldn't save the sender.`}</p> : null}
    {save.isSuccess ? <p role="status" className="text-sm">{t`Sender saved.`}</p> : null}
    <button type="submit" className="desk-button-primary justify-self-start" disabled={save.isPending}>{save.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : t`Save sender`}</button>
  </form>;
}

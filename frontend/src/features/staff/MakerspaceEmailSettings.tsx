import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ErrorBlock, SettingsRow } from "../../components/ui";
import { SettingsResetAction } from "./SettingsResetAction";
import { SettingsQueryState } from "./SettingsQueryState";
import { SettingsEditorActions } from "./SettingsEditorActions";
import { staffRequest } from "../../lib/api";
import { type Makerspace, useStaffGet } from "./StaffPanels";
import { EmailTransportFields } from "../deployment/EmailTransportFields";
import { useEmailSettings } from "../deployment/useEmailSettings";

type NotificationRecipient = {
  id: number;
  username: string;
  email: string;
  role: "space_manager" | "inventory_manager" | "machine_manager" | "event_manager" | "booking_manager" | "handover" | "shop_manager";
  receives_notifications: boolean;
};


export function MakerspaceEmailSettings({ makerspace }: { makerspace: Makerspace }) {
  // Changing tenants unmounts drafts and in-flight mutation observers with their secrets.
  return <MakerspaceEmailEditor key={makerspace.id} makerspace={makerspace} />;
}

function MakerspaceEmailEditor({ makerspace }: { makerspace: Makerspace }) {
  const queryClient = useQueryClient();
  const editor = useEmailSettings(`/admin/makerspace/${makerspace.id}/api-settings`, ["api-settings", makerspace.id], false);
  const [recipientChecks, setRecipientChecks] = useState<Record<number, boolean>>({});
  const [recipientsDirty, setRecipientsDirty] = useState(false);
  const recipients = useStaffGet<NotificationRecipient[]>(["notification-recipients", makerspace.id],
    `/admin/makerspace/${makerspace.id}/notification-recipients`);
  useEffect(() => {
    if (!recipients.data) return;
    setRecipientChecks(Object.fromEntries(recipients.data.map(recipient => [recipient.id, recipient.receives_notifications])));
    setRecipientsDirty(false);
  }, [recipients.data]);
  const saveRecipients = useMutation({
    mutationFn: () =>
      staffRequest<NotificationRecipient[]>(
        `/admin/makerspace/${makerspace.id}/notification-recipients`,
        {
          method: "PATCH",
          body: JSON.stringify({
            recipients: (recipients.data ?? []).map((recipient) => ({
              id: recipient.id,
              receives_notifications:
                recipientChecks[recipient.id] ?? recipient.receives_notifications,
            })),
          }),
        },
      ),
    onSuccess: (updated) => {
      setRecipientChecks(
        Object.fromEntries(
          updated.map((recipient) => [recipient.id, recipient.receives_notifications]),
        ),
      );
      setRecipientsDirty(false);
      queryClient.invalidateQueries({ queryKey: ["notification-recipients", makerspace.id] });
    },
  });

  return <>
    <SettingsQueryState query={editor.settings} resource="email settings">
      <SettingsRow label="Email delivery" helper="Select the sender used for tenant notifications.">
        <div className="@container grid min-w-0 gap-4">
          <EmailTransportFields form={editor.form} onChange={editor.setForm} platform={false}
            disabled={!editor.settings.isSuccess || editor.save.isPending}
            configured={editor.settings.data?.email_provider_configured} passwordSet={editor.settings.data?.smtp_password_set} />
          {editor.validation ? <p className="text-sm text-danger">{editor.validation}</p> : null}
          {editor.save.error ? <p className="text-sm text-danger" role="alert">{editor.save.error.message}</p> : null}
          <SettingsEditorActions dirty={editor.dirty} onDiscard={editor.discard} pending={editor.save.isPending}
            disabled={!editor.settings.isSuccess || !!editor.validation} onSave={() => editor.save.mutate()} />
          {editor.form.provider === "smtp" ? <SettingsResetAction label="Clear SMTP password"
            consequence="Remove the saved SMTP password. Email delivery may stop until a replacement is saved."
            pending={editor.clearPassword.isPending} disabled={!editor.settings.data?.smtp_password_set || editor.save.isPending}
            onConfirm={() => editor.clearPassword.mutateAsync()} /> : null}
          {editor.clearPassword.error ? <p className="text-sm text-danger" role="alert">{editor.clearPassword.error.message}</p> : null}
        </div>
      </SettingsRow>
    </SettingsQueryState>
      <SettingsQueryState query={recipients} resource="notification recipients"><SettingsRow label="Notification recipients" helper="Unchecked managers will not receive hardware/printing lifecycle emails for this makerspace."><div className="@container grid min-w-0 gap-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="grid max-w-2xl gap-2">


          </div>
          <SettingsEditorActions dirty={recipientsDirty} onDiscard={() => { setRecipientChecks(Object.fromEntries((recipients.data ?? []).map(recipient => [recipient.id, recipient.receives_notifications]))); setRecipientsDirty(false); }} pending={saveRecipients.isPending} disabled={!recipients.isSuccess || !recipientsDirty || saveRecipients.isPending || !recipients.data?.length} onSave={() => saveRecipients.mutate()} />
        </div>
        {recipients.isLoading ? <p className="mt-3 text-sm text-muted">Loading recipients…</p> : null}
        <div className="mt-4 grid gap-2">
          {recipients.data?.map((recipient) => (
            <label
              key={recipient.id}
              className="min-h-11 flex items-start gap-3 rounded-md border border-line bg-surface p-3 text-sm text-ink"
            >
              <input
                className="mt-1 h-4 w-4"
                type="checkbox"
                checked={recipientChecks[recipient.id] ?? recipient.receives_notifications}
                onChange={(event) => {
                  setRecipientChecks({
                    ...recipientChecks,
                    [recipient.id]: event.target.checked,
                  });
                  setRecipientsDirty(true);
                }}
              />
              <span>
                <span className="font-semibold">{recipient.username}</span>
                <span className="block text-muted">
                  {recipient.email} - {roleLabel(recipient.role)}
                </span>
              </span>
            </label>
          ))}
        </div>
        {!recipients.isLoading && recipients.data?.length === 0 ? (
          <p className="mt-3 text-sm text-muted">No managers to notify yet.</p>
        ) : null}
        {recipients.error ? <ErrorBlock error={new Error("Couldn't load notification recipients. Try again.")} onRetry={() => { void recipients.refetch(); }} /> : null}
        {saveRecipients.error ? (
          <p className="mt-3 text-sm text-danger">{saveRecipients.error.message}</p>
        ) : null}
      </div></SettingsRow></SettingsQueryState>
  </>;
}

function roleLabel(role: NotificationRecipient["role"]) {
  return {
    space_manager: "Space manager",
    inventory_manager: "Inventory manager",
    machine_manager: "Machine manager",
    event_manager: "Event manager",
    booking_manager: "Booking manager",
    handover: "Handover",
    shop_manager: "Shop manager",
  }[role];
}

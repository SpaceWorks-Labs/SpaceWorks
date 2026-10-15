import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ConfirmDialog, DangerZone, ErrorBlock, Skeleton, SettingsActions, SettingsRow, StatusPill } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import { type Makerspace, useStaffGet } from "./StaffPanels";
type ApiSettings = {
  telegram_group_chat_id: string;
  telegram_bot_token_set: boolean;
};
type TelegramSettingsForm = {
  telegram_group_chat_id: string;
  telegram_bot_token: string;
};

export function ApiClientsTelegramSettings({ makerspace }: { makerspace: Makerspace }) {
  const queryClient = useQueryClient();
  const [confirmClear, setConfirmClear] = useState(false);
  const [settingsForm, setSettingsForm] = useState<TelegramSettingsForm>({
    telegram_group_chat_id: "",
    telegram_bot_token: "",
  });
  const settings = useStaffGet<ApiSettings>(
    ["api-settings", makerspace.id],
    `/admin/makerspace/${makerspace.id}/api-settings`,
  );
  useEffect(() => {
    if (!settings.data) return;
    setSettingsForm({
      telegram_group_chat_id: settings.data.telegram_group_chat_id ?? "",
      telegram_bot_token: "",
    });
  }, [settings.data]);
  const saveSettings = useMutation({
    mutationFn: () =>
      staffRequest<ApiSettings>(`/admin/makerspace/${makerspace.id}/api-settings`, {
        method: "PATCH",
        body: JSON.stringify(settingsPayload(settingsForm)),
      }),
    onSuccess: () => {
      setSettingsForm((current) => ({
        ...current,
        telegram_bot_token: "",
      }));
      queryClient.invalidateQueries({ queryKey: ["api-settings", makerspace.id] });
    },
  });
  const clearTelegramToken = useMutation({
    mutationFn: () =>
      staffRequest<ApiSettings>(`/admin/makerspace/${makerspace.id}/api-settings`, {
        method: "PATCH",
        body: JSON.stringify({ telegram_bot_token: "" }),
      }),
    onSuccess: () => {
      setSettingsForm((current) => ({ ...current, telegram_bot_token: "" }));
      queryClient.invalidateQueries({ queryKey: ["api-settings", makerspace.id] });
    },
  });
  const testTelegram = useMutation({
    mutationFn: () =>
      staffRequest<{ delivered: boolean; detail?: string }>("/integrations/telegram/test-alert", {
        method: "POST",
        body: JSON.stringify({
          makerspace_id: makerspace.id,
          message: `Test alert from ${makerspace.name}`,
        }),
      }),
  });
  return (
    <div className="rounded-md border border-line bg-surface p-3">
      <h3 className="title-section">Telegram</h3>
      <StatusPill label={settings.data?.telegram_bot_token_set ? "Token saved" : "No token saved"} />
      <div className="mt-3 divide-y divide-line">
        <SettingsRow label="Telegram group chat ID" htmlFor="telegram-group">
          <input
            id="telegram-group" className="desk-input"
            value={settingsForm.telegram_group_chat_id}
            onChange={(event) =>
              setSettingsForm({ ...settingsForm, telegram_group_chat_id: event.target.value })
            }
          />
        </SettingsRow>
        <SettingsRow label="Telegram bot token" htmlFor="telegram-token">
          <input
            id="telegram-token" className="desk-input"
            placeholder={settings.data?.telegram_bot_token_set ? "Telegram bot token set" : undefined}
            type="password"
            value={settingsForm.telegram_bot_token}
            onChange={(event) =>
              setSettingsForm({ ...settingsForm, telegram_bot_token: event.target.value })
            }
          />
        </SettingsRow>
      </div>
      {settingsForm.telegram_bot_token || settingsForm.telegram_group_chat_id !== (settings.data?.telegram_group_chat_id ?? "") || saveSettings.error ?
        <SettingsActions pending={saveSettings.isPending} disabled={!settings.isSuccess} onSave={() => saveSettings.mutate()}
          onDiscard={() => setSettingsForm({ telegram_group_chat_id: settings.data?.telegram_group_chat_id ?? "", telegram_bot_token: "" })} /> : null}
      <button
        className="desk-button mt-2 w-full"
        disabled={!settings.isSuccess || testTelegram.isPending}
        onClick={() => testTelegram.mutate()}
      >
        {testTelegram.isPending ? "Sending…" : "Send Telegram test alert"}
      </button>
      {settings.isLoading ? <Skeleton className="mt-3 h-24 w-full" /> : null}
      {settings.error ? <ErrorBlock error={new Error("Couldn't load Telegram settings. Try again.")} onRetry={() => { void settings.refetch(); }} /> : null}
      {saveSettings.error ? <p className="mt-2 text-sm text-danger">{saveSettings.error.message}</p> : null}
      {clearTelegramToken.error ? <p className="mt-2 text-sm text-danger">{clearTelegramToken.error.message}</p> : null}
      {testTelegram.data ? (
        <p className={`mt-2 text-sm ${testTelegram.data.delivered ? "text-muted" : "text-danger"}`}>
          Telegram delivered: {testTelegram.data.delivered ? "yes" : "no"}
          {!testTelegram.data.delivered && testTelegram.data.detail ? ` - ${testTelegram.data.detail}` : ""}
        </p>
      ) : null}
      {testTelegram.error ? <p className="mt-2 text-sm text-danger">{testTelegram.error.message}</p> : null}
      <DangerZone title="Clear Telegram token" consequence="Stops Telegram alerts for this makerspace until a new token is saved."
        action={{ label: "Clear Telegram token", disabled: !settings.data?.telegram_bot_token_set || clearTelegramToken.isPending, onClick: () => setConfirmClear(true) }} />
      <ConfirmDialog open={confirmClear} title="Clear Telegram token?" message="Telegram alerts will stop until a new token is saved." confirmLabel="Clear token" tone="danger"
        pending={clearTelegramToken.isPending} onCancel={() => setConfirmClear(false)} onConfirm={() => { clearTelegramToken.mutate(); setConfirmClear(false); }} />
    </div>
  );
}

function settingsPayload(form: TelegramSettingsForm) {
  const payload: Record<string, string> = {
    telegram_group_chat_id: form.telegram_group_chat_id,
  };
  if (form.telegram_bot_token) payload.telegram_bot_token = form.telegram_bot_token;
  return payload;
}

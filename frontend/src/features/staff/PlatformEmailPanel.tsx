import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { SettingsRow, StatusPill } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import { PlatformConfigurationSection } from "./PlatformConfigurationSection";
import { useStaffGet } from "./StaffPanels";
type PlatformEmailSettings = {
  id: number;
  smtp_host: string;
  smtp_port: number;
  smtp_username: string;
  smtp_password_set: boolean;
  smtp_use_tls: boolean;
  smtp_use_ssl: boolean;
  from_email: string;
  updated_at: string;
};
type PlatformEmailForm = {
  smtp_host: string;
  smtp_port: string;
  smtp_username: string;
  smtp_password: string;
  smtp_use_tls: boolean;
  smtp_use_ssl: boolean;
  from_email: string;
};

export function PlatformEmailPanel({ embedded = false }: { embedded?: boolean }) {
  const queryClient = useQueryClient();
  const settings = useStaffGet<PlatformEmailSettings>(
    ["platform-email"],
    "/admin/platform/email-settings",
  );
  const [form, setForm] = useState<PlatformEmailForm>({
    smtp_host: "",
    smtp_port: "587",
    smtp_username: "",
    smtp_password: "",
    smtp_use_tls: true,
    smtp_use_ssl: false,
    from_email: "",
  });
  const [savedForm, setSavedForm] = useState(form);
  useEffect(() => {
    if (!settings.data) return;
    const next = {
      smtp_host: settings.data.smtp_host ?? "",
      smtp_port: String(settings.data.smtp_port ?? 587),
      smtp_username: settings.data.smtp_username ?? "",
      smtp_password: "",
      smtp_use_tls: settings.data.smtp_use_tls,
      smtp_use_ssl: settings.data.smtp_use_ssl,
      from_email: settings.data.from_email ?? "",
    };
    setForm(next); setSavedForm(next);
  }, [settings.data]);
  const save = useMutation({
    mutationFn: () =>
      staffRequest<PlatformEmailSettings>("/admin/platform/email-settings", {
        method: "PATCH",
        body: JSON.stringify(platformEmailPayload(form)),
      }),
    onSuccess: () => {
      setForm((current) => ({ ...current, smtp_password: "" }));
      queryClient.invalidateQueries({ queryKey: ["platform-email"] });
    },
  });
  const formDisabled = settings.isLoading || save.isPending;
  return <PlatformConfigurationSection title="Platform email" subtitle="Instance-wide SMTP for password resets and spaces without their own email settings." embedded={embedded}
    state={{ status: settings.isLoading ? "loading" : settings.error ? "error" : "ready", error: "Couldn't load platform email. Try again.", onRetry: () => { void settings.refetch(); } }}
    save={{ dirty: JSON.stringify(form) !== JSON.stringify(savedForm), pending: save.isPending, error: save.error?.message,
      onDiscard: () => { setForm(savedForm); save.reset(); }, onSave: () => save.mutate() }}>
    <StatusPill label={settings.data?.smtp_host.trim() ? "SMTP host configured" : "Not configured"} tone={settings.data?.smtp_host.trim() ? "success" : "neutral"} />
    <div className="divide-y divide-line">
          <SettingsRow label="SMTP host"><input aria-label="SMTP host" className="desk-input w-full" disabled={formDisabled} value={form.smtp_host} onChange={(event) => setForm({ ...form, smtp_host: event.target.value })} /></SettingsRow>
          <SettingsRow label="SMTP port"><input aria-label="SMTP port" className="desk-input w-full" disabled={formDisabled} inputMode="numeric" value={form.smtp_port} onChange={(event) => setForm({ ...form, smtp_port: event.target.value })} /></SettingsRow>
          <SettingsRow label="SMTP username"><input aria-label="SMTP username" className="desk-input w-full" disabled={formDisabled} value={form.smtp_username} onChange={(event) => setForm({ ...form, smtp_username: event.target.value })} /></SettingsRow>
          <SettingsRow label="SMTP password"><input aria-label="SMTP password" className="desk-input w-full" disabled={formDisabled} placeholder={settings.data?.smtp_password_set ? "SMTP password set" : undefined} type="password" value={form.smtp_password} onChange={(event) => setForm({ ...form, smtp_password: event.target.value })} /></SettingsRow>
          <SettingsRow label="From email"><input aria-label="From email" className="desk-input w-full" disabled={formDisabled} value={form.from_email} onChange={(event) => setForm({ ...form, from_email: event.target.value })} /></SettingsRow>
        <div className="flex flex-wrap gap-4">
          <label className="flex min-h-11 items-center gap-2 text-sm text-muted">
            <input
              type="checkbox"
              disabled={formDisabled}
              checked={form.smtp_use_tls}
              onChange={(event) => setForm({ ...form, smtp_use_tls: event.target.checked })}
            />
            Use STARTTLS (587)
          </label>
          <label className="flex min-h-11 items-center gap-2 text-sm text-muted">
            <input
              type="checkbox"
              disabled={formDisabled}
              checked={form.smtp_use_ssl}
              onChange={(event) => setForm({ ...form, smtp_use_ssl: event.target.checked })}
            />
            Use implicit SSL (465)
          </label>
        </div>
    </div>
  </PlatformConfigurationSection>;
}

function platformEmailPayload(form: PlatformEmailForm) {
  const payload: Record<string, string | number | boolean> = {
    smtp_host: form.smtp_host,
    smtp_port: Number(form.smtp_port) || 587,
    smtp_username: form.smtp_username,
    smtp_use_tls: form.smtp_use_tls,
    smtp_use_ssl: form.smtp_use_ssl,
    from_email: form.from_email,
  };
  if (form.smtp_password) payload.smtp_password = form.smtp_password;
  return payload;
}

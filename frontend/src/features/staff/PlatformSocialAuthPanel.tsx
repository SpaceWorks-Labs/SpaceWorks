import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../lib/api";
import { SettingsRow } from "../../components/ui";
import { PlatformConfigurationSection } from "./PlatformConfigurationSection";
import { useStaffGet } from "./StaffPanels";
type SocialSettings = {
  google_enabled: boolean;
  apple_enabled: boolean;
  github_enabled: boolean;
  google_web_client_id: string;
  google_ios_client_id: string;
  google_android_client_id: string;
  apple_service_id: string;
  apple_native_app_ids: string[];
  apple_team_id: string;
  apple_key_id: string;
  apple_private_key_set: boolean;
  github_client_id: string;
  github_client_secret_set: boolean;
};

export function PlatformSocialAuthPanel({ embedded = false }: { embedded?: boolean }) {
  const queryClient = useQueryClient();
  const settings = useStaffGet<SocialSettings>(["platform-social-auth"], "/admin/platform/social-auth-settings");
  const [form, setForm] = useState({
    google_web_client_id: "",
    google_ios_client_id: "",
    google_android_client_id: "",
    apple_service_id: "",
    apple_native_app_ids: "",
    apple_team_id: "",
    apple_key_id: "",
    apple_private_key: "",
    github_client_id: "",
    github_client_secret: "",
    clear_github_client_secret: false,
  });
  const [savedForm, setSavedForm] = useState(form);
  useEffect(() => {
    if (!settings.data) return;
    const next = {
      google_web_client_id: settings.data.google_web_client_id,
      google_ios_client_id: settings.data.google_ios_client_id,
      google_android_client_id: settings.data.google_android_client_id,
      apple_service_id: settings.data.apple_service_id,
      apple_native_app_ids: settings.data.apple_native_app_ids.join("\n"),
      apple_team_id: settings.data.apple_team_id,
      apple_key_id: settings.data.apple_key_id,
      apple_private_key: "",
      github_client_id: settings.data.github_client_id,
      github_client_secret: "",
      clear_github_client_secret: false,
    };
    setForm(next); setSavedForm(next);
  }, [settings.data]);
  const save = useMutation({
    mutationFn: () => staffRequest<SocialSettings>("/admin/platform/social-auth-settings", {
      method: "PATCH",
      // Only the providers this deployment installed are sent; an uninstalled provider's
      // fields are hidden, so writing them would change settings nobody can see.
      body: JSON.stringify(Object.fromEntries(Object.entries({
        ...form,
        apple_native_app_ids: form.apple_native_app_ids.split(/[,\n]/).map((item) => item.trim()).filter(Boolean),
        ...(form.apple_private_key ? {} : { apple_private_key: undefined }),
        ...(form.github_client_secret ? {} : { github_client_secret: undefined }),
      }).filter(([key]) => key.includes("github") ? settings.data?.github_enabled
        : key.startsWith("google_") ? settings.data?.google_enabled : settings.data?.apple_enabled))),
    }),
    onSuccess: () => {
      setForm((current) => ({ ...current, apple_private_key: "", github_client_secret: "", clear_github_client_secret: false }));
      void queryClient.invalidateQueries({ queryKey: ["platform-social-auth"] });
    },
  });
  const disabled = !settings.data || save.isPending;
  const anyProvider = Boolean(settings.data && (settings.data.google_enabled || settings.data.apple_enabled || settings.data.github_enabled));
  return (
    <PlatformConfigurationSection title="Social sign-in" subtitle="Platform identities link to global accounts; memberships grant each space’s permissions." embedded={embedded}
      state={{ status: settings.isLoading ? "loading" : settings.error ? "error" : "ready", error: "Couldn't load sign-in providers. Try again.", onRetry: () => { void settings.refetch(); } }}
      save={{ dirty: JSON.stringify(form) !== JSON.stringify(savedForm), pending: save.isPending, error: save.error?.message,
        onSave: () => save.mutate(), onDiscard: () => { setForm(savedForm); save.reset(); } }}>
      <p className="text-sm text-muted">
        Platform-wide identities link to global accounts; makerspace permissions still come from each membership.
      </p>
      {settings.data ? <div className="mt-2 text-sm text-muted">
        {settings.data.google_enabled ? <p>Google: {[settings.data.google_web_client_id, settings.data.google_ios_client_id, settings.data.google_android_client_id].some((id) => id.trim()) ? "Client IDs configured" : "Not configured"}</p> : null}
        {settings.data.apple_enabled ? <p>Apple: {settings.data.apple_service_id.trim() || settings.data.apple_native_app_ids.length ? "Audiences configured" : "Not configured"}</p> : null}
        {settings.data.github_enabled ? <p>GitHub: {settings.data.github_client_id.trim() && settings.data.github_client_secret_set ? "OAuth App configured" : "Not configured"}</p> : null}
        {!anyProvider ? <p>No social sign-in provider was installed on this deployment.</p> : null}
      </div> : null}
      <div className="mt-4 grid gap-5 divide-y divide-line [&>*+*]:pt-5">
        {settings.data?.github_enabled ? <fieldset disabled={disabled} className="space-y-3">
          <legend className="font-semibold text-ink">GitHub OAuth App (members)</legend>
          <LabeledInput label="GitHub client ID" value={form.github_client_id} onChange={(value) => setForm({ ...form, github_client_id: value })} />
          <SettingsRow label="GitHub client secret"><input aria-label="GitHub client secret" type="password" autoComplete="new-password" className="desk-input w-full"
            value={form.github_client_secret} disabled={form.clear_github_client_secret}
            onChange={(event) => setForm({ ...form, github_client_secret: event.target.value })}
            placeholder={settings.data.github_client_secret_set ? "Secret set — leave blank to keep it" : "Paste the client secret"} /></SettingsRow>
          <label className="flex min-h-11 items-center gap-2 text-sm text-muted">
            <input type="checkbox" checked={form.clear_github_client_secret}
              onChange={(event) => setForm({ ...form, clear_github_client_secret: event.target.checked, github_client_secret: "" })} />
            Clear saved GitHub secret
          </label>
        </fieldset> : null}
        {settings.data?.google_enabled ? <fieldset disabled={disabled} className="space-y-3">
          <legend className="font-semibold text-ink">Google OAuth clients</legend>
          <LabeledInput label="Web client ID" value={form.google_web_client_id} onChange={(value) => setForm({ ...form, google_web_client_id: value })} />
          <div className="grid gap-3">
            <LabeledInput label="iOS client ID" value={form.google_ios_client_id} onChange={(value) => setForm({ ...form, google_ios_client_id: value })} />
            <LabeledInput label="Android client ID" value={form.google_android_client_id} onChange={(value) => setForm({ ...form, google_android_client_id: value })} />
          </div>
        </fieldset> : null}
        {settings.data?.apple_enabled ? <fieldset disabled={disabled} className="space-y-3">
          <legend className="font-semibold text-ink">Apple Sign in</legend>
          <LabeledInput label="Web Service ID" value={form.apple_service_id} onChange={(value) => setForm({ ...form, apple_service_id: value })} />
          <label className="block text-sm font-semibold text-ink">Native app audiences
            <textarea className="desk-input mt-1 min-h-20 w-full" value={form.apple_native_app_ids} onChange={(event) => setForm({ ...form, apple_native_app_ids: event.target.value })} placeholder="One audience per line" />
          </label>
          <div className="grid gap-3">
            <LabeledInput label="Team ID" value={form.apple_team_id} onChange={(value) => setForm({ ...form, apple_team_id: value })} />
            <LabeledInput label="Key ID" value={form.apple_key_id} onChange={(value) => setForm({ ...form, apple_key_id: value })} />
          </div>
          <label className="block text-sm font-semibold text-ink">Apple private key (.p8)
            <textarea className="desk-input mt-1 min-h-24 w-full code-text text-base md:text-xs" value={form.apple_private_key} onChange={(event) => setForm({ ...form, apple_private_key: event.target.value })} placeholder={settings.data?.apple_private_key_set ? "Private key set — leave blank to keep it" : "Paste the private key"} />
          </label>
        </fieldset> : null}
      </div>
    </PlatformConfigurationSection>
  );
}

function LabeledInput({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <SettingsRow label={label}><input aria-label={label} className="desk-input w-full" value={value} onChange={(event) => onChange(event.target.value)} /></SettingsRow>;
}

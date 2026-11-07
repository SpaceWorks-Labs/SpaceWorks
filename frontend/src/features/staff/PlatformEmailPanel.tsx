import { t } from "@lingui/core/macro";
import { StatusPill } from "../../components/ui";
import { EmailTransportFields } from "../deployment/EmailTransportFields";
import { useEmailSettings } from "../deployment/useEmailSettings";
import { PlatformConfigurationSection } from "./PlatformConfigurationSection";

export function PlatformEmailPanel({ embedded = false }: { embedded?: boolean }) {
  const editor = useEmailSettings("/admin/platform/email-settings", ["platform-email"], true);
  return <PlatformConfigurationSection title={t`Platform email`}
    subtitle={t`Instance-wide email for authentication, password resets and spaces that inherit platform delivery.`}
    embedded={embedded} state={{ status: editor.settings.isLoading ? "loading" : editor.settings.error ? "error" : "ready",
      error: t`Couldn't load platform email. Try again.`, onRetry: () => { void editor.settings.refetch(); } }}
    save={{ dirty: editor.dirty, pending: editor.save.isPending, error: editor.save.error?.message,
      disabled: !editor.settings.isSuccess || !!editor.validation, onDiscard: editor.discard, onSave: () => editor.save.mutate() }}>
    <StatusPill label={editor.settings.data?.email_provider_configured || editor.settings.data?.smtp_host
      ? t`Configuration saved; verify delivery with your provider` : t`Using deployment configuration`} />
    <EmailTransportFields form={editor.form} onChange={editor.setForm} platform
      disabled={!editor.settings.isSuccess || editor.save.isPending}
      configured={editor.settings.data?.email_provider_configured} passwordSet={editor.settings.data?.smtp_password_set} />
    {editor.validation ? <p className="text-sm text-danger">{editor.validation}</p> : null}
  </PlatformConfigurationSection>;
}

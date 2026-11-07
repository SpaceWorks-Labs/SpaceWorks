import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { SettingsRow, SettingsSection } from "../../components/ui";
import { presenceApi, presenceKeys, type PresencePrivacy } from "./api";
import { presenceErrorText } from "./presenceCopy";

/** Presence display privacy (Space Manager; server requires manage_makerspace). Exported for the
 * settings shell to mount; render it only when the `presence` module is enabled. */
export function PresencePrivacySettings({ makerspaceId, slug }: { makerspaceId: number; slug?: string }) {
  const client = useQueryClient();
  const key = presenceKeys.privacy(makerspaceId);
  const privacy = useQuery({ queryKey: key, queryFn: () => presenceApi.privacy(makerspaceId) });
  const save = useMutation({
    mutationFn: (next: Partial<PresencePrivacy>) => presenceApi.savePrivacy(makerspaceId, next),
    onSuccess: (data) => client.setQueryData(key, data),
  });
  const value = privacy.data;
  const toggle = (field: keyof PresencePrivacy, label: string) => <label className="flex min-h-11 items-center gap-3 text-sm">
    <input type="checkbox" role="switch" className="h-5 w-5 accent-accent" aria-label={label} checked={Boolean(value?.[field])}
      disabled={!value || save.isPending || (field === "allow_personal_opt_out" && !value.show_names)}
      onChange={(event) => save.mutate({ [field]: event.target.checked })} />
    <span>{value?.[field] ? t`On` : t`Off`}</span>
  </label>;
  return <SettingsSection title={t`Presence display`} description={t`Controls the public “who's in” screen${slug ? ` at /m/${slug}/now` : ""}. It never shows contact details or history.`}>
    {privacy.isLoading ? <p role="status" className="py-4 text-sm text-muted">{t`Loading presence settings…`}</p> : null}
    {privacy.isError ? <p role="alert" className="py-4 text-sm text-danger">{presenceErrorText(privacy.error).text}</p> : null}
    {value ? <>
      <SettingsRow label={t`Show names`} helper={t`Off: everyone appears as “A member” or “A guest”, with no project or event titles.`}>{toggle("show_names", "Show names on the display")}</SettingsRow>
      <SettingsRow label={t`Let people hide their name`} helper={value.show_names
        ? t`On: anyone can choose to appear anonymously. Off: names are always shown, and people are told so when they check in.`
        : t`Only applies while names are shown.`}>{toggle("allow_personal_opt_out", "Let people hide their name")}</SettingsRow>
    </> : null}
    {save.error ? <p role="alert" className="py-3 text-sm text-danger">{presenceErrorText(save.error).text}</p> : null}
  </SettingsSection>;
}

import { LogoLoader } from "../../../components/LogoLoader";
import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ErrorText, Field } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";
import { ImageUploader } from "../ImageUploader";
import { MakerspaceHoursEditor } from "../MakerspaceHoursEditor";
import { hoursDraft, serializeHours, validateHours, type MakerspaceProfile } from "../makerspaceProfileForm";
import { StaffRoleFields, validRoleSet, type RoleDraft } from "../panels/staffRoles/StaffRoleEditor";
import { deliveryText, grantStaffRole, listStaffRoles, staffRoleErrorText } from "../panels/staffRoles/staffRolesApi";
import type { Makerspace } from "../panels/shared";
import { BoxArt } from "../../../components/BoxSpinner";

/** Each step saves through the same endpoint its Settings page uses, then refreshes setup progress. */
type StepProps = { makerspace: Makerspace; onSaved: () => void };

function useRefresh(space: number) {
  const client = useQueryClient();
  return (...keys: unknown[][]) => {
    for (const key of [["setup-state", space], ["staff", "makerspaces"], ["makerspaces"], ["makerspace-settings", space], ...keys]) {
      void client.invalidateQueries({ queryKey: key });
    }
  };
}

const message = (error: unknown) => error instanceof Error ? error.message : t`Something went wrong. Try again.`;

export function NameStep({ makerspace, onSaved }: StepProps) {
  const refresh = useRefresh(makerspace.id);
  const [name, setName] = useState(makerspace.name);
  const save = useMutation({
    mutationFn: () => staffRequest(`/admin/makerspaces/${makerspace.id}`, { method: "PATCH", body: JSON.stringify({ name: name.trim() }) }),
    onSuccess: () => { refresh(); onSaved(); },
  });
  return <form id="first-run-step" className="grid gap-3" onSubmit={event => {
    event.preventDefault();
    if (name.trim() === makerspace.name.trim()) onSaved();
    else if (name.trim()) save.mutate();
  }}>
    <Field label={t`Space name`} hint={t`You can change it later in Settings › Profile & location.`}>
      <input className="desk-input w-full" required maxLength={200} value={name} disabled={save.isPending} onChange={event => setName(event.target.value)} />
    </Field>
    {save.error ? <ErrorText message={message(save.error)} /> : null}
  </form>;
}

export function LogoStep({ makerspace }: StepProps) {
  const refresh = useRefresh(makerspace.id);
  return <div className="grid gap-3">
    <ImageUploader endpoint={`/admin/makerspace/${makerspace.id}/logo`} currentUrl={makerspace.logo_url} label={t`Logo`} fit="contain"
      onChanged={() => refresh(["public-makerspaces"], ["tenant-bootstrap"])} />
    <p className="text-sm text-muted">{t`A square image works best. You can replace it any time in Settings › Branding & public site.`}</p>
  </div>;
}

export function HoursStep({ makerspace, onSaved }: StepProps) {
  const refresh = useRefresh(makerspace.id);
  const client = useQueryClient();
  const path = `/admin/makerspace/${makerspace.id}/profile`;
  const profile = useQuery({ queryKey: ["makerspace-profile", makerspace.id], queryFn: () => staffRequest<MakerspaceProfile>(path) });
  const [hours, setHours] = useState(() => hoursDraft({}));
  const [invalid, setInvalid] = useState<string | null>(null);
  useEffect(() => {
    if (!profile.data) return;
    const current = hoursDraft(profile.data.opening_hours);
    // Nothing set yet: start from a weekday 09:00-17:00 week the manager can adjust.
    const weekday = [{ start: "09:00", end: "17:00" }];
    setHours(current.configured || current.exceptions.length ? current : {
      ...current, configured: true, weekly: { ...current.weekly, mon: weekday, tue: weekday, wed: weekday, thu: weekday, fri: weekday },
    });
  }, [profile.data]);
  const save = useMutation({
    mutationFn: () => staffRequest<MakerspaceProfile>(path, { method: "PATCH", body: JSON.stringify({ opening_hours: serializeHours(hours) }) }),
    onSuccess: updated => { client.setQueryData(["makerspace-profile", makerspace.id], updated); refresh(); onSaved(); },
  });
  if (profile.isPending) return <LogoLoader label={t`Loading your hours…`} />;
  if (profile.error) return <ErrorText message={t`Couldn't load your hours. Skip this step and set them later in Settings.`} />;
  return <form id="first-run-step" className="grid gap-3" onSubmit={event => {
    event.preventDefault();
    const problem = validateHours(hours);
    setInvalid(problem);
    if (!problem) save.mutate();
  }}>
    <p className="text-sm text-muted">{t`Times use ${profile.data.timezone}. Change the timezone in Settings › Profile & location.`}</p>
    <MakerspaceHoursEditor value={hours} onChange={value => { setHours(value); setInvalid(null); }} />
    {invalid ? <ErrorText message={invalid} /> : null}
    {save.error ? <ErrorText message={message(save.error)} /> : null}
  </form>;
}

export function StaffStep({ makerspace }: StepProps) {
  const roles = useQuery({ queryKey: ["staff-roles", makerspace.id, "wizard"], queryFn: () => listStaffRoles(makerspace.id, 1, false) });
  const refresh = useRefresh(makerspace.id);
  const [email, setEmail] = useState("");
  const [draft, setDraft] = useState<RoleDraft>({ roles: [], machine_type_ids: [], machine_ids: [] });
  const [sent, setSent] = useState<string[]>([]);
  const [notice, setNotice] = useState("");
  const invite = useMutation({
    mutationFn: () => grantStaffRole(makerspace.id, { email: email.trim(), ...draft }),
    onSuccess: result => {
      setSent(list => [...list, email.trim()]); setNotice(deliveryText(result.delivery_status));
      setEmail(""); setDraft({ roles: [], machine_type_ids: [], machine_ids: [] }); refresh(["staff", "invitations", makerspace.id]);
    },
  });
  if (roles.isPending) return <LogoLoader label={t`Loading staff roles…`} />;
  if (roles.error) return <ErrorText message={staffRoleErrorText(roles.error)} />;
  const policy = roles.data.policy;
  if (!policy.email_invites_available) {
    return <p className="text-sm text-muted">{t`Email is not set up on this server yet, so invitations can't be sent. Skip this step; you can invite staff later from People › Staff & roles.`}</p>;
  }
  const ready = email.trim().length > 0 && validRoleSet(policy, draft.roles);
  return <form id="first-run-invite" className="grid gap-3" onSubmit={event => { event.preventDefault(); if (ready && !invite.isPending) invite.mutate(); }}>
    <fieldset disabled={invite.isPending} className="grid min-w-0 gap-3">
      <legend className="sr-only">{t`Invite a staff member`}</legend>
      <Field label={t`Their email`} hint={t`They accept while signed in, or create an account with this address.`}>
        <input className="desk-input w-full" type="email" maxLength={254} autoComplete="off" value={email} onChange={event => setEmail(event.target.value)} />
      </Field>
      <StaffRoleFields policy={policy} draft={draft} onChange={setDraft} />
    </fieldset>
    <button type="submit" className="desk-button w-fit" disabled={!ready || invite.isPending}>{invite.isPending ? <><BoxArt size={16} mono />{t`Sending…`}</> : t`Send invitation`}</button>
    {invite.error ? <ErrorText message={staffRoleErrorText(invite.error)} /> : null}
    {notice ? <p role="status" className="text-sm">{notice}</p> : null}
    {sent.length ? <p className="text-sm text-muted">{t`Invited so far: ${sent.join(", ")}`}</p> : null}
  </form>;
}

import { t } from "@lingui/core/macro";
import { useState } from "react";

import { Card } from "../../components/ui";
import { AsyncSearchPicker, type PickerOption } from "./AsyncSearchPicker";
import { useAssignSpeaker, useInviteSpeaker, useSpeakerCandidates } from "./eventSpeakersApi";
import { panelField, panelInput, panelReveal } from "./eventPanelStyles";
import { eventErrorText } from "./eventUi";

export type SpeakerSection = { slug: string; title: string };
const RELATION = { member: "Member", staff: "Staff", registrant: "Registered for this event" } as const;

/** Links an optional website speaker profile; offered only when the event website has one. */
function SectionSelect({ sections, value, onChange, disabled }: { sections: SpeakerSection[]; value: string; onChange: (slug: string) => void; disabled: boolean }) {
  if (!sections.length) return null;
  return <label className={panelField}>{t`Website speaker profile (optional)`}<select className={panelInput} value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)}>
      <option value="">{t`Not linked`}</option>{sections.map((row) => <option key={row.slug} value={row.slug}>{row.title || row.slug}</option>)}
    </select></label>;
}

function CheckInToggle({ checked, onChange, disabled }: { checked: boolean; onChange: (value: boolean) => void; disabled: boolean }) {
  return <label className="flex min-h-11 items-center gap-2 text-sm text-ink"><input type="checkbox" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />{t`Also allow check-in`}</label>;
}

/** Assign an existing account: a member, staff member or registrant found by search. */
export function AssignSpeakerForm({ eventId, sections, disabled }: { eventId: number; sections: SpeakerSection[]; disabled: boolean }) {
  const [term, setTerm] = useState("");
  const [picked, setPicked] = useState<PickerOption | null>(null);
  const [section, setSection] = useState("");
  const [checkIn, setCheckIn] = useState(true);
  const candidates = useSpeakerCandidates(eventId, term);
  const assign = useAssignSpeaker(eventId);
  const options = (term.length >= 2 ? candidates.data?.results ?? [] : []).map((row) => ({ id: row.id, label: row.display_name || row.username, detail: `${row.username} · ${RELATION[row.relation] ?? row.relation}` }));
  return <Card><form className="grid gap-4" aria-label={t`Assign a speaker`} onSubmit={(e) => {
    e.preventDefault();
    if (!picked) return;
    assign.mutate({ user_id: picked.id, grant_check_in: checkIn, ...(section ? { section_slug: section } : {}) }, { onSuccess: () => { setPicked(null); setSection(""); } });
  }}>
    <h4 className="title-section">{t`Assign an account`}</h4>
    <AsyncSearchPicker label={t`Speaker account`} helper="Search members, staff and people registered for this event. Type at least two characters."
      placeholder={t`Search by name or username`} selected={picked ? [picked] : []} options={options}
      loading={term.length >= 2 && candidates.isFetching} error={candidates.error ? eventErrorText(candidates.error) : null}
      emptyText={term.length >= 2 ? t`No matching accounts.` : t`Type at least two characters.`}
      onSearch={setTerm} onChange={(next) => setPicked(next[next.length - 1] ?? null)} disabled={disabled} />
    <SectionSelect sections={sections} value={section} onChange={setSection} disabled={disabled} />
    <CheckInToggle checked={checkIn} onChange={setCheckIn} disabled={disabled} />
    {assign.error ? <p role="alert" className="text-sm text-danger">{eventErrorText(assign.error)}</p> : null}
    <button className="desk-button-primary justify-self-start" type="submit" disabled={disabled || !picked || assign.isPending}>{assign.isPending ? t`Assigning…` : t`Assign speaker`}</button>
  </form></Card>;
}

/** For a speaker without an account here yet: a one-time link they claim after signing in. */
export function InviteSpeakerForm({ eventId, sections, disabled }: { eventId: number; sections: SpeakerSection[]; disabled: boolean }) {
  const [name, setName] = useState("");
  const [section, setSection] = useState("");
  const [checkIn, setCheckIn] = useState(true);
  const [claimUrl, setClaimUrl] = useState("");
  const [copied, setCopied] = useState("");
  const invite = useInviteSpeaker(eventId);
  return <Card><form className="grid gap-4" aria-label={t`Create a speaker claim link`} onSubmit={(e) => {
    e.preventDefault();
    invite.mutate({ display_name: name.trim(), grant_check_in: checkIn, ...(section ? { section_slug: section } : {}) }, {
      onSuccess: (data) => { setClaimUrl(data.claim_url); setCopied(""); setName(""); setSection(""); },
    });
  }}>
    <h4 className="title-section">{t`Create claim link`}</h4>
    <p className="text-sm text-muted">{t`The speaker opens the link, signs in or creates an account, and is linked to this event.`}</p>
    <label className={panelField}>{t`Speaker name`}<input className={panelInput} required maxLength={200} value={name} disabled={disabled} onChange={(e) => setName(e.target.value)} /></label>
    <SectionSelect sections={sections} value={section} onChange={setSection} disabled={disabled} />
    <CheckInToggle checked={checkIn} onChange={setCheckIn} disabled={disabled} />
    {invite.error ? <p role="alert" className="text-sm text-danger">{eventErrorText(invite.error)}</p> : null}
    <button className="desk-button-primary justify-self-start" type="submit" disabled={disabled || !name.trim() || invite.isPending}>{invite.isPending ? t`Creating…` : t`Create claim link`}</button>
  </form>
    {claimUrl ? <div role="status" className={`${panelReveal} mt-4`}>
      <p>{t`Copy this link now. It is shown once and works for one account.`}</p>
      <output className="break-all code-text">{claimUrl}</output>
      <div className="flex flex-wrap gap-2">
        <button className="desk-button" type="button" onClick={async () => {
          try { await navigator.clipboard.writeText(claimUrl); setCopied("Link copied."); }
          catch { setCopied("Copy failed. Select the link and copy it."); }
        }}>{t`Copy link`}</button>
        <button className="desk-button" type="button" onClick={() => setClaimUrl("")}>{t`Hide link`}</button>
      </div>
      {copied ? <p className="text-sm">{copied}</p> : null}
    </div> : null}
  </Card>;
}

import { plural, t } from "@lingui/core/macro";
import { Award, Building2, ShieldCheck, Users } from "lucide-react";
import { RouteLink } from "../../../components/ui/RouteLink";
import type { AccountProfile, TimelineKind, TimelineRow } from "../accountProfileTypes";
import { safeProfileHref, timelineRange } from "../profileFormat";
import { TIMELINE_COPY } from "../timelineCopy";
import { ProfileSection } from "./ProfileSection";
import { monthYear, statusLabel, verifiedSentence } from "./profileCopy";

type Props = { profile: AccountProfile };
const base = (profile: AccountProfile) => ({ shown: profile.shown, audience: profile.audience });

export function StatusSection({ profile }: Props) {
  const status = profile.status;
  if (!status || (!status.preset && !status.note)) return null;
  return <ProfileSection id="status" title={t`Status`} section="status" {...base(profile)}>
    <div className="flex flex-wrap items-center gap-3">
      {status.preset ? <span className="chip text-sm font-semibold">{statusLabel(status.preset)}</span> : null}
      {status.note ? <p className="break-words text-ink">{status.note}</p> : null}
    </div>
  </ProfileSection>;
}

export function AboutSection({ profile }: Props) {
  if (!profile.bio) return null;
  return <ProfileSection id="about" title={t`About`} section="about" {...base(profile)}>
    <p className="max-w-prose whitespace-pre-line break-words text-ink">{profile.bio}</p>
  </ProfileSection>;
}

/** Spaces first (with a standard role title), then organizations that are not already listed as spaces. */
export function SpacesSection({ profile }: Props) {
  const orgs = profile.organizations.filter(org => !profile.spaces.some(space => space.kind === "organization" && space.slug === org.slug));
  const vouchers = profile.vouched_by ?? [];
  const unnamed = Math.max(0, (profile.vouched_count ?? 0) - vouchers.length);
  if (!profile.spaces.length && !orgs.length && !vouchers.length && !unnamed) return null;
  return <ProfileSection id="spaces" title={t`Spaces and organizations`} section="spaces" {...base(profile)}>
    <ul className="grid gap-3 sm:grid-cols-2">
      {profile.spaces.map(space => <li key={`${space.kind}-${space.slug}`} className="flex min-h-11 items-center gap-3 rounded-control border border-line p-3">
        <span aria-hidden="true" className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-soft text-brand-ink">
          {space.kind === "organization" ? <Building2 className="h-4 w-4" /> : <Users className="h-4 w-4" />}</span>
        <span className="grid min-w-0">
          <RouteLink href={space.kind === "organization" ? `/o/${space.slug}` : `/m/${space.slug}`} className="break-words font-semibold text-ink underline-offset-2 hover:underline">{space.name}</RouteLink>
          {space.role_title ? <span className="text-sm text-muted">{space.role_title}</span> : null}
        </span>
      </li>)}
      {orgs.map(org => <li key={`org-${org.slug}`} className="flex min-h-11 items-center gap-3 rounded-control border border-line p-3">
        <span aria-hidden="true" className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent-soft text-accent-ink"><Building2 className="h-4 w-4" /></span>
        <RouteLink href={`/o/${org.slug}`} className="break-words font-semibold text-ink underline-offset-2 hover:underline">{org.name}</RouteLink>
      </li>)}
    </ul>
    {vouchers.length || unnamed ? <p className="text-sm text-muted">
      {vouchers.length ? <>{t`Vouched for by `}{vouchers.map((voucher, index) => <span key={voucher.handle}>{index ? ", " : ""}
        <RouteLink href={`/${voucher.handle}`} className="font-semibold text-ink underline-offset-2 hover:underline">{voucher.display_name}</RouteLink>
        {voucher.space_name ? ` (${voucher.space_name})` : ""}</span>)}</> : null}
      {vouchers.length && unnamed ? " · " : null}
      {unnamed ? plural(unnamed, { one: "# more vouch", other: "# more vouches" }) : null}
    </p> : null}
  </ProfileSection>;
}

function Timeline({ rows }: { rows: TimelineRow[] }) {
  return <ol className="grid gap-6">{rows.map((entry, index) => {
    const { Icon, tone, title } = TIMELINE_COPY[entry.kind];
    return <li key={entry.id ?? index} className="grid grid-cols-[2.25rem_1fr] gap-x-3 gap-y-1">
      <span aria-hidden="true" className={`inline-flex h-9 w-9 items-center justify-center rounded-full ${tone}`}><Icon className="h-4 w-4" /></span>
      <p className="self-center text-sm text-muted">{timelineRange(entry.start, entry.end)}{entry.kind === "volunteering" ? ` · ${title}` : ""}</p>
      <div className="col-start-2 grid gap-1">
        <h3 className="title-section break-words">{entry.title}</h3>
        {entry.organization || entry.location ? <p className="text-sm text-muted">{[entry.organization, entry.location].filter(Boolean).join(" · ")}</p> : null}
        {entry.description ? <p className="whitespace-pre-line break-words text-sm text-ink">{entry.description}</p> : null}
      </div>
    </li>;
  })}</ol>;
}

const byKinds = (rows: TimelineRow[], kinds: TimelineKind[]) => rows.filter(row => kinds.includes(row.kind));

export function ExperienceSection({ profile }: Props) {
  const rows = byKinds(profile.timeline, ["experience", "volunteering"]);
  if (!rows.length) return null;
  return <ProfileSection id="experience" title={t`Experience`} section="experience" {...base(profile)}><Timeline rows={rows} /></ProfileSection>;
}

export function EducationSection({ profile }: Props) {
  const rows = byKinds(profile.timeline, ["education"]);
  if (!rows.length && !profile.education.length) return null;
  return <ProfileSection id="education" title={t`Education`} section="education" {...base(profile)}>
    {rows.length ? <Timeline rows={rows} /> : null}
    {profile.education.length ? <ul className="grid gap-2 text-sm text-ink">{profile.education.map((row, index) => <li key={index} className="break-words">
      {[row.qualification, row.institution, row.year].filter(Boolean).join(" · ")}</li>)}</ul> : null}
  </ProfileSection>;
}

/** Verified rows come from the platform and carry the space that vouches; self-reported ones are the member's word. */
export function AchievementsSection({ profile }: Props) {
  const { verified, self_reported: own } = profile.achievements;
  if (!verified.length && !own.length) return null;
  return <ProfileSection id="achievements" title={t`Achievements`} section="achievements" {...base(profile)}>
    <ul className="grid gap-3">
      {verified.map((row, index) => <li key={`v-${index}`} className="flex flex-wrap items-start gap-3 rounded-control border border-line p-3">
        <ShieldCheck aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0 text-success-ink" />
        <div className="grid min-w-0 flex-1 gap-1">
          <p className="break-words font-semibold text-ink">{verifiedSentence(row)}</p>
          {row.occurred_on ? <p className="text-sm text-muted">{monthYear(row.occurred_on)}</p> : null}
        </div>
        <span className="chip bg-success-soft text-success-ink">{t`Verified by ${row.verified_by}`}</span>
      </li>)}
      {own.map((row, index) => <li key={`s-${row.id ?? index}`} className="flex flex-wrap items-start gap-3 rounded-control border border-line p-3">
        <Award aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0 text-muted" />
        <div className="grid min-w-0 flex-1 gap-1">
          <p className="break-words font-semibold text-ink">{safeProfileHref(row.url)
            ? <a href={safeProfileHref(row.url)} target="_blank" rel="noopener noreferrer nofollow ugc" className="underline-offset-2 hover:underline">{row.title}</a> : row.title}</p>
          <p className="text-sm text-muted">{[row.issuer, row.achieved_on ? monthYear(row.achieved_on) : ""].filter(Boolean).join(" · ")}</p>
          {row.description ? <p className="whitespace-pre-line break-words text-sm text-ink">{row.description}</p> : null}
        </div>
        <span className="chip">{t`Self-reported`}</span>
      </li>)}
    </ul>
  </ProfileSection>;
}

export function CertificationsSection({ profile }: Props) {
  if (!profile.certifications.length) return null;
  return <ProfileSection id="certifications" title={t`Certifications`} section="certifications" {...base(profile)}>
    <ul className="flex flex-wrap gap-2">{profile.certifications.map((row, index) => <li key={index} className="chip">
      {row.space_name ? t`${row.name} · ${row.space_name}` : row.name}</li>)}</ul>
  </ProfileSection>;
}

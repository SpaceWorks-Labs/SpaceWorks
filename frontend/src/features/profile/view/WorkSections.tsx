import { plural, t } from "@lingui/core/macro";
import { CalendarCheck } from "lucide-react";
import type { AccountProfile, ProfileSkill } from "../accountProfileTypes";
import { domainIcon, linkPresentation, safeProfileHref, skillLevelLabel } from "../profileFormat";
import { ProfileSection } from "./ProfileSection";
import { EventsHistory } from "./ActivitySection";
import { eventDate } from "./profileCopy";

type Props = { profile: AccountProfile };
const base = (profile: AccountProfile) => ({ shown: profile.shown, audience: profile.audience });

export function ProjectsSection({ profile }: Props) {
  if (!profile.projects.length) return null;
  return <ProfileSection id="projects" title={t`Projects`} section="projects" {...base(profile)}>
    <ul className="grid gap-4 md:grid-cols-2">
      {profile.projects.map((project, index) => <li key={project.id ?? index} className="desk-panel grid content-start gap-3 p-4">
        {project.image_url ? <img src={project.image_url} alt="" className="aspect-video w-full rounded-lg bg-hover object-cover" /> : null}
        <div>
          <h3 className="title-section break-words">{project.title}</h3>
          {project.subtitle ? <p className="font-semibold text-muted">{project.subtitle}</p> : null}
          {project.imported ? <span className="chip mt-1">{t`From a hackathon submission`}</span> : null}
          {base(profile).audience === "owner" && !project.public_visible ? <span className="chip mt-1">{t`Hidden from others`}</span> : null}
        </div>
        {project.description ? <p className="whitespace-pre-line break-words text-sm text-ink">{project.description}</p> : null}
        {project.tags.length ? <ul aria-label={t`Tags`} className="flex flex-wrap gap-2">{project.tags.map(tag => <li key={tag} className="chip">{tag}</li>)}</ul> : null}
        {project.links.some(link => safeProfileHref(link.url)) ? <ul className="flex flex-wrap gap-3 text-sm">{project.links.filter(link => safeProfileHref(link.url)).map(link => <li key={link.url}>
          <a href={safeProfileHref(link.url)} target="_blank" rel="noopener noreferrer nofollow ugc" className="font-semibold text-accent-ink underline-offset-2 hover:underline">
            {link.label || linkPresentation({ kind: "", url: link.url }).label} ↗</a></li>)}</ul> : null}
      </li>)}
    </ul>
  </ProfileSection>;
}

export function EventsSection({ profile }: Props) {
  const events = profile.events_attended;
  if (!events || !events.count) return null;
  return <ProfileSection id="events" title={t`Events attended`} section="events" {...base(profile)}>
    <p className="text-sm text-muted">{plural(events.count, { one: "# public event attended", other: "# public events attended" })}</p>
    {events.recent.length ? <ul className="grid gap-2">{events.recent.map(event => <li key={event.id} className="flex flex-wrap items-center gap-3">
      <CalendarCheck aria-hidden="true" className="h-4 w-4 text-brand-ink" />
      <span className="break-words font-semibold text-ink">{event.title}</span>
      <span className="text-sm text-muted">{[eventDate(event.starts_at), event.space_name].filter(Boolean).join(" · ")}</span>
    </li>)}</ul> : null}
    {profile.handle ? <EventsHistory handle={profile.handle} /> : null}
  </ProfileSection>;
}

function SkillDots({ level }: { level: number }) {
  return <span role="img" aria-label={t`${skillLevelLabel(level)} (${level} of 3)`} title={skillLevelLabel(level)} className="flex gap-1">
    {[1, 2, 3].map(dot => <span key={dot} aria-hidden="true" className={`h-2.5 w-2.5 rounded-full ${dot <= level ? dot === 3 ? "bg-success-ink" : "bg-success" : "bg-hover"}`} />)}
  </span>;
}

function SkillList({ skills }: { skills: ProfileSkill[] }) {
  return <ul className="grid gap-x-8 gap-y-3 sm:grid-cols-2">{skills.map(skill => <li key={skill.name} className="flex min-h-11 items-center justify-between gap-3">
    <span className="break-words font-semibold text-ink">{skill.name}</span><SkillDots level={skill.level} /></li>)}</ul>;
}

/** Skills with their domains; interests and languages sit under it as plain chips (their own switch). */
export function SkillsSection({ profile }: Props) {
  if (!profile.skills.length && !profile.domains.length) return null;
  return <ProfileSection id="skills" title={t`Skills`} section="skills" {...base(profile)}>
    {profile.domains.length ? <ul aria-label={t`Domains`} className="flex flex-wrap gap-2">{profile.domains.map(domain => {
      const Glyph = domainIcon(domain);
      return <li key={domain} className="inline-flex min-h-9 items-center gap-2 rounded-full border border-line bg-surface px-3 text-sm font-semibold text-ink">
        <Glyph aria-hidden="true" className="h-4 w-4 text-brand-ink" />{domain}</li>;
    })}</ul> : null}
    {profile.skills.length ? <SkillList skills={profile.skills} /> : null}
  </ProfileSection>;
}

export function InterestsSection({ profile }: Props) {
  if (!profile.interests.length && !profile.languages.length) return null;
  return <ProfileSection id="interests" title={t`Interests and languages`} section="interests" {...base(profile)}>
    {profile.interests.length ? <ul aria-label={t`Interests`} className="flex flex-wrap gap-2">{profile.interests.map(item => <li key={item} className="chip">{item}</li>)}</ul> : null}
    {profile.languages.length ? <ul aria-label={t`Languages`} className="flex flex-wrap gap-2">{profile.languages.map(item => <li key={item} className="chip">{item}</li>)}</ul> : null}
  </ProfileSection>;
}

export function LinksSection({ profile }: Props) {
  const links = profile.links.filter(link => safeProfileHref(link.url));
  if (!links.length) return null;
  return <ProfileSection id="links" title={t`Links`} section="links" {...base(profile)}>
    <ul className="flex flex-wrap gap-2">{links.map(link => {
      const { label, Icon } = linkPresentation(link);
      return <li key={link.url}><a href={safeProfileHref(link.url)} target="_blank" rel="noopener noreferrer nofollow ugc" aria-label={t`${label} (opens in a new tab)`} title={label}
        className="desk-button min-h-11 min-w-11 gap-2 rounded-full px-3"><Icon aria-hidden="true" className="h-4 w-4" /><span className="text-sm">{label}</span></a></li>;
    })}</ul>
  </ProfileSection>;
}

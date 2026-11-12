import { plural, t } from "@lingui/core/macro";
import { useState } from "react";
import { ErrorBlock } from "../../../components/ui";
import type { AccountProfile } from "../accountProfileTypes";
import { GitHubIdentity } from "./GitHubIdentity";
import { usePublicProfileActivity, usePublicProfileEvents, usePublicProfileGithub } from "../publicProfileApi";
import { ContributionGrid } from "./ContributionGrid";
import { eventDate } from "./profileCopy";
import { ProfileSection } from "./ProfileSection";
import { LogoLoader } from "../../../components/LogoLoader";

const BADGES = () => ({ ATTENDED: t`Attended`, HOSTED: t`Hosted`, SPOKE: t`Spoke` });

/** Hosted, spoke and attended public events, a page at a time. Empty unless the member switched events on. */
export function EventsHistory({ handle }: { handle: string }) {
  const [open, setOpen] = useState(false);
  const [page, setPage] = useState(1);
  const events = usePublicProfileEvents(handle, page, open);
  const badge = BADGES();
  return <div className="grid gap-3">
    <button type="button" className="desk-button w-fit" aria-expanded={open} onClick={() => setOpen(value => !value)}>{open ? t`Hide events history` : t`Show events history`}</button>
    {open && events.isLoading ? <LogoLoader size={48} className="min-h-16 py-3" /> : null}
    {open && events.error ? <ErrorBlock error={new Error(t`Couldn't load events. Try again.`)} onRetry={() => { void events.refetch(); }} /> : null}
    {open && events.data && !events.data.results.length ? <p className="text-sm text-muted">{t`No past events yet.`}</p> : null}
    {open && events.data?.results.length ? <ul className="grid gap-2">{events.data.results.map((event, index) => <li key={`${event.starts_at}-${index}`} className="flex flex-wrap items-center gap-3">
      <span className="chip">{badge[event.badge] ?? event.badge}</span>
      <span className="break-words font-semibold text-ink">{event.title}</span>
      <span className="text-sm text-muted">{[eventDate(event.starts_at), event.host].filter(Boolean).join(" · ")}</span>
    </li>)}</ul> : null}
    {open && (events.data?.previous || events.data?.next) ? <div className="flex gap-2">
      <button type="button" className="desk-button" disabled={!events.data?.previous} onClick={() => setPage(value => value - 1)}>{t`Previous`}</button>
      <button type="button" className="desk-button" disabled={!events.data?.next} onClick={() => setPage(value => value + 1)}>{t`Next`}</button>
    </div> : null}
  </div>;
}

/** Counts-only activity across the person's spaces, plus their own GitHub calendar, labelled separately (different sources). */
export function ActivitySection({ profile }: { profile: AccountProfile }) {
  const handle = profile.handle ?? "";
  const on = Boolean(handle) && Boolean(profile.activity_shown);
  const activity = usePublicProfileActivity(handle, on);
  const github = usePublicProfileGithub(handle, on && Boolean(profile.github_username) && Boolean(profile.github_verified));
  const identity = Boolean(profile.github_username);
  if (!on || (!activity.data?.days.length && !github.data?.days.length && !identity)) return null;
  return <ProfileSection id="activity" title={t`Activity`} section="projects" shown={{ ...profile.shown, projects: true }} audience={profile.audience}>
    <GitHubIdentity username={profile.github_username ?? ""} verified={Boolean(profile.github_verified)} />
    {activity.data?.days.length ? <ContributionGrid title={t`Activity on Space Works`} days={activity.data.days} tone="brand"
      describe={(total, days) => plural(total, { one: `# activity in the past ${days} days`, other: `# activities in the past ${days} days` })} /> : null}
    {github.data?.days.length ? <ContributionGrid title={t`GitHub contributions`} days={github.data.days} tone="success"
      describe={(total, days) => plural(total, { one: `# contribution in the past ${days} days`, other: `# contributions in the past ${days} days` })} /> : null}
  </ProfileSection>;
}

import { ErrorBlock, Skeleton } from "../../components/ui";
import { ContributionGrid } from "./ContributionGrid";
import { skillLevelLabel } from "./profileFormat";
import { usePublicProfileActivity, usePublicProfileGithub, type ProfileSkill, type PublicProfile } from "./publicProfileApi";

function SkillDots({ level }: { level: number }) {
  return <span role="img" aria-label={`${skillLevelLabel(level)} (${level} of 3)`} title={skillLevelLabel(level)} className="flex gap-1">
    {[1, 2, 3].map(dot => <span key={dot} aria-hidden="true"
      className={`h-2.5 w-2.5 rounded-full ${dot <= level ? dot === 3 ? "bg-success-ink" : "bg-success" : "bg-hover"}`} />)}
  </span>;
}

export function SkillList({ skills }: { skills: ProfileSkill[] }) {
  if (!skills.length) return null;
  return <section aria-labelledby="profile-skills" className="grid gap-3">
    <h3 id="profile-skills" className="title-section">Skills and languages</h3>
    <ul className="grid gap-x-8 gap-y-3 sm:grid-cols-2">
      {skills.map(skill => <li key={skill.name} className="flex min-h-11 items-center justify-between gap-3">
        <span className="flex min-w-0 items-center gap-3">
          <span aria-hidden="true" className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-control border border-line bg-surface text-xs font-semibold uppercase text-brand-ink">
            {Array.from(skill.name.trim()).slice(0, 2).join("")}</span>
          <span className="break-words font-semibold text-ink">{skill.name}</span>
        </span>
        <SkillDots level={skill.level} />
      </li>)}
    </ul>
  </section>;
}

function SpaceWorksActivity({ handle }: { handle: string }) {
  const activity = usePublicProfileActivity(handle, true);
  if (activity.isLoading) return <Skeleton className="h-36" />;
  if (activity.error) return <ErrorBlock error={new Error("Couldn't load activity. Try again.")} onRetry={() => { void activity.refetch(); }} />;
  if (!activity.data?.days.length) return null;
  return <ContributionGrid title="Activity on Space Works" days={activity.data.days} tone="brand" unit={["activity", "activities"]} />;
}

/** Labelled separately: GitHub's numbers are GitHub's, not this platform's. Absent endpoint = no graph. */
function GithubActivity({ handle }: { handle: string }) {
  const github = usePublicProfileGithub(handle, true);
  if (!github.data?.days.length) return null;
  return <ContributionGrid title="GitHub contributions" days={github.data.days} tone="success" unit={["contribution", "contributions"]} />;
}

export function ProfileOverviewTab({ profile, preview }: { profile: PublicProfile; preview: boolean }) {
  const graphs = profile.show_activity_graph && !preview;
  const empty = !profile.skills.length && !graphs;
  return <div className="grid gap-8">
    {graphs ? <SpaceWorksActivity handle={profile.handle} /> : null}
    {graphs ? <GithubActivity handle={profile.handle} /> : null}
    {preview && profile.show_activity_graph ? <p className="text-sm text-muted">Your activity graph appears here once the page is published.</p> : null}
    <SkillList skills={profile.skills} />
    {empty ? <p className="text-sm text-muted">Nothing else shared yet.</p> : null}
  </div>;
}

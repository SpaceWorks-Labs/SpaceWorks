import type { ReactNode } from "react";
import { Briefcase, FolderGit2, GraduationCap, HeartHandshake, Plus, type LucideIcon } from "lucide-react";
import { RouteLink } from "../../components/ui/RouteLink";
import { linkPresentation, timelineRange } from "./profileFormat";
import type { PublicProject, PublicTimelineEntry, TimelineKind } from "./publicProfileApi";

function AddLink({ href, label }: { href?: string; label: string }) {
  return href ? <RouteLink href={href} aria-label={label} className="desk-button gap-2 rounded-full">Add<Plus aria-hidden="true" className="h-4 w-4" /></RouteLink> : null;
}

function SectionHeading({ id, title, addHref, addLabel }: { id: string; title: string; addHref?: string; addLabel: string }) {
  return <div className="flex flex-wrap items-center justify-between gap-3">
    <h2 id={id} className="title-panel">{title}</h2><AddLink href={addHref} label={addLabel} />
  </div>;
}

function Empty({ Icon, tone, message, addHref, addLabel }: { Icon: LucideIcon; tone: string; message: string; addHref?: string; addLabel: string }) {
  return <div className="flex min-h-48 flex-col items-center justify-center gap-4 rounded-2xl border border-dashed border-line p-6 text-center">
    <span aria-hidden="true" className={`inline-flex h-12 w-12 items-center justify-center rounded-full ${tone}`}><Icon className="h-5 w-5" /></span>
    <p className="max-w-sm text-[15px] text-muted">{message}</p>
    <AddLink href={addHref} label={addLabel} />
  </div>;
}

export function ProfileProjectsTab({ projects, addHref }: { projects: PublicProject[]; addHref?: string }) {
  return <section aria-labelledby="profile-projects" className="grid gap-4">
    <SectionHeading id="profile-projects" title="Projects" addHref={projects.length ? addHref : undefined} addLabel="Add a project" />
    {!projects.length ? <Empty Icon={FolderGit2} tone="bg-brand-soft text-brand-ink" addHref={addHref} addLabel="Add a project"
      message={addHref ? "Show what you've built. Add a project and mark it public." : "No public projects yet."} /> : null}
    <ul className="grid gap-4 md:grid-cols-2">
      {projects.map((project, index) => <li key={`${project.title}-${index}`} className="desk-panel grid content-start gap-3 p-4">
        {project.image_url ? <img src={project.image_url} alt="" className="aspect-video w-full rounded-lg bg-hover object-cover" /> : null}
        <div><h3 className="title-section break-words">{project.title}</h3>
          {project.subtitle ? <p className="font-semibold text-muted">{project.subtitle}</p> : null}</div>
        {project.description ? <p className="whitespace-pre-line break-words text-sm text-ink">{project.description}</p> : null}
        {project.tags.length ? <ul aria-label="Tags" className="flex flex-wrap gap-2">{project.tags.map(tag => <li key={tag} className="chip">{tag}</li>)}</ul> : null}
        {project.links.length ? <ul className="flex flex-wrap gap-3 text-sm">{project.links.map(link => <li key={link.url}>
          <a href={link.url} target="_blank" rel="noopener noreferrer nofollow ugc" className="font-semibold text-accent-ink underline-offset-2 hover:underline">
            {linkPresentation(link).label} ↗</a></li>)}</ul> : null}
      </li>)}
    </ul>
  </section>;
}

export const TIMELINE_COPY: Record<TimelineKind, { title: string; Icon: LucideIcon; tone: string; owner: string; visitor: string }> = {
  experience: { title: "Experience", Icon: Briefcase, tone: "bg-info-soft text-info-ink",
    owner: "Build your professional story. Add your work history.", visitor: "No experience shared yet." },
  education: { title: "Education", Icon: GraduationCap, tone: "bg-warn-soft text-warn-ink",
    owner: "Add the schools, courses and programmes you've studied.", visitor: "No education shared yet." },
  volunteering: { title: "Volunteering", Icon: HeartHandshake, tone: "bg-accent-soft text-accent-ink",
    owner: "Add the communities and causes you give time to.", visitor: "No volunteering shared yet." },
};

export function ProfileTimelineTab({ kind, entries, addHref }: { kind: TimelineKind; entries: PublicTimelineEntry[]; addHref?: string }) {
  const copy = TIMELINE_COPY[kind];
  const rows = entries.filter(entry => entry.kind === kind);
  let body: ReactNode;
  if (!rows.length) body = <Empty Icon={copy.Icon} tone={copy.tone} message={addHref ? copy.owner : copy.visitor} addHref={addHref} addLabel={`Add ${copy.title.toLowerCase()}`} />;
  else body = <ol className="grid gap-6">{rows.map((entry, index) => <li key={`${entry.start}-${index}`} className="grid grid-cols-[2.25rem_1fr] gap-x-3 gap-y-1">
    <span aria-hidden="true" className={`inline-flex h-9 w-9 items-center justify-center rounded-full ${copy.tone}`}><copy.Icon className="h-4 w-4" /></span>
    <p className="self-center text-sm text-muted">{timelineRange(entry.start, entry.end)}</p>
    <div className="col-start-2 grid gap-1">
      <h3 className="title-section break-words">{entry.title}</h3>
      {entry.organization || entry.location ? <p className="text-sm text-muted">{[entry.organization, entry.location].filter(Boolean).join(" · ")}</p> : null}
      {entry.description ? <p className="whitespace-pre-line break-words text-sm text-ink">{entry.description}</p> : null}
    </div>
  </li>)}</ol>;
  return <section aria-labelledby={`profile-${kind}`} className="grid gap-4">
    <SectionHeading id={`profile-${kind}`} title={copy.title} addHref={rows.length ? addHref : undefined} addLabel={`Add ${copy.title.toLowerCase()}`} />
    {body}
  </section>;
}

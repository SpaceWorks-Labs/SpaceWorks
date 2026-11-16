import { t } from "@lingui/core/macro";
import { Avatar } from "../../../components/ui";
import { RouteLink } from "../../../components/ui/RouteLink";
import { PageMetadata } from "../../../components/PageMetadata";
import { formatDate } from "../../../lib/format";
import { useOptionalTenant } from "../../../lib/tenant";
import type { PublicAccountCard } from "../publicProfileApi";

/** Render only the public allow-list, including when the viewer owns the account. */
export function PublicProfileCard({ profile }: { profile: PublicAccountCard }) {
  const tenant = useOptionalTenant();
  return <article className="grid min-w-0 gap-6 text-ink">
    {profile.handle ? <PageMetadata title={profile.display_name} description={profile.bio || t`Profile on Space Works`}
      path={`/@${profile.handle}`} image={profile.avatar_url} imageAlt={profile.display_name} /> : null}
    <header className="flex flex-wrap items-center gap-4">
      {profile.avatar_url ? <img src={profile.avatar_url} alt="" className="h-24 w-24 rounded-full border border-line object-cover" />
        : <Avatar name={profile.display_name} seed={profile.handle ?? profile.display_name} size="lg" />}
      <div className="grid min-w-0 gap-2">
        <h1 className="break-words font-accent text-ink">{profile.display_name}</h1>
        {profile.handle ? <p className="text-sm text-muted">@{profile.handle}</p> : null}
      </div>
    </header>
    {profile.bio ? <section aria-label={t`About`} className="grid gap-3">
      <h2 className="text-xl font-semibold">{t`About`}</h2>
      <p className="whitespace-pre-wrap break-words text-muted">{profile.bio}</p>
    </section> : null}
    {profile.projects?.length ? <section aria-label={t`Projects`} className="grid gap-3">
      <h2 className="text-xl font-semibold">{t`Projects`}</h2>
      <ul className="grid gap-4 sm:grid-cols-2">{profile.projects.map((project, index) => <li key={index} className="grid min-w-0 content-start gap-2 rounded-xl border border-line bg-surface p-4">
        {project.image_url ? <img src={project.image_url} alt="" loading="lazy" className="aspect-video w-full rounded-lg object-cover" /> : null}
        <h3 className="break-words font-semibold">{project.title}</h3>
        {project.subtitle ? <p className="break-words text-sm text-muted">{project.subtitle}</p> : null}
        <p className="whitespace-pre-wrap break-words text-sm text-muted">{project.description}</p>
        <div className="flex flex-wrap gap-2">{project.tags.map(tag => <span key={tag} className="chip">{tag}</span>)}</div>
        {project.links.map((link, linkIndex) => <a key={linkIndex} href={link.url} target="_blank" rel="noopener noreferrer"
          className="break-all text-sm font-semibold text-accent-ink underline-offset-2 hover:underline">{link.kind}</a>)}
      </li>)}</ul>
    </section> : null}
    {profile.memberships?.length ? <section aria-label={t`Memberships`} className="grid gap-3">
      <h2 className="text-xl font-semibold">{t`Memberships`}</h2>
      <ul className="grid gap-3">{profile.memberships.map(membership => <li key={membership.slug} className="flex flex-wrap items-start justify-between gap-2 rounded-xl border border-line p-4">
        <div className="grid min-w-0 gap-1">
          {tenant?.mode === "single" && membership.slug !== tenant.slug
            ? <span className="break-words font-semibold">{membership.name}</span>
            : <RouteLink href={tenant?.mode === "single" ? "/" : `/m/${membership.slug}`} className="break-words font-semibold text-accent-ink underline-offset-2 hover:underline">{membership.name}</RouteLink>}
          {membership.role_title ? <p className="text-sm text-muted">{membership.role_title}</p> : null}
        </div>
        <p className="text-sm text-muted">{t`Member since ${formatDate(membership.started_on, { dateStyle: "medium", timeZone: "UTC" })}`}</p>
      </li>)}</ul>
    </section> : null}
  </article>;
}

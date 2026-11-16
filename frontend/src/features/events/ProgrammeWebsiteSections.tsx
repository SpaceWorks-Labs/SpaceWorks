import { t } from "@lingui/core/macro";
import { websiteSectionHeading, type EventWebsite } from "./websiteTypes";

const text = (value: unknown) => typeof value === "string" ? value : "";
const photo = (value: unknown) => typeof value === "string" && /^\/api\/v1\/public\/event-programmes\/[a-f0-9-]{36}\/member-cards\/[a-f0-9-]{36}\/photo\/$/.test(value) ? value : null;
const profile = (value: unknown) => typeof value === "string" && /^\/[a-z0-9][a-z0-9._-]{1,28}[a-z0-9]$/.test(value) ? value : null;
export function ProgrammeWebsiteSections({ rows }: { rows: EventWebsite["programme_sections"] }) {
  return <>{rows?.map((section, index) => <section key={`${section.kind}-${index}`} aria-label={websiteSectionHeading(section.kind)} className="grid gap-3">
    <h2 className="title-panel">{websiteSectionHeading(section.kind)}</h2>
    <div className={section.layout === "grid" ? "grid gap-3 sm:grid-cols-2" : "grid gap-3"}>{section.items.map((item, position) => <article key={position} className="grid gap-2 rounded-xl border border-line bg-panel p-5">
      {photo(item.photo_url) ? <img className="h-16 w-16 rounded-full object-cover" src={photo(item.photo_url)!} alt="" loading="lazy" /> : null}
      <h3 className="title-section">{text(item.title) || text(item.display_name) || text(item.name) || text(item.prize)}</h3>
      {text(item.description) ? <p className="whitespace-pre-line text-sm text-muted">{text(item.description)}</p> : null}
      {typeof item.rank === "number" ? <p className="text-sm">{t`Rank ${item.rank}`}</p> : null}
      {profile(item.profile_url) ? <a className="desk-button justify-self-start" href={profile(item.profile_url)!}>{t`View public profile`}</a> : null}
      {Array.isArray(item.assets) ? item.assets.map((asset: Record<string, unknown>, n: number) => typeof asset.download_url === "string" && asset.download_url.startsWith("/api/v1/public/event-programmes/") ? <a key={n} className="desk-button justify-self-start" href={asset.download_url}>{text(asset.kind) ? t`Download ${text(asset.kind)}` : t`Download project file`}</a> : null) : null}
    </article>)}</div>
  </section>)}</>;
}

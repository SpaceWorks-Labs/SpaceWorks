import { formatLocale } from "../../lib/format";
import { plural, t } from "@lingui/core/macro";
import { DetailDrawer, EmptyState, ListRow } from "../../components/ui";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { memberRequest } from "../../lib/api";
import type { MemberProfile } from "./MemberProfilePanel";

type DirectoryEntry = {
  membership_id: number;
  display_name: string;
  headline: string;
  avatar_url: string | null;
};

type Directory = { members: DirectoryEntry[]; hidden_count: number };

const IDENTITY_TONES = [
  { border: "border-accent", surface: "bg-accent-soft", ink: "text-accent-ink" },
  { border: "border-brand", surface: "bg-brand-soft", ink: "text-brand-ink" },
  { border: "border-success", surface: "bg-success-soft", ink: "text-success-ink" },
  { border: "border-warn", surface: "bg-warn-soft", ink: "text-warn-ink" },
] as const;

function identityTone(identity: string | number) {
  const text = String(identity);
  const total = [...text].reduce((sum, character) => sum + character.codePointAt(0)!, 0);
  return IDENTITY_TONES[total % IDENTITY_TONES.length];
}

/**
 * Who else is here — but only the people who chose to be listed.
 *
 * The row carries a display name and an avatar and nothing else: the backend does not
 * send contact details on this endpoint at all, because otherwise "see who else is here"
 * is an address harvest available to anyone the space admits.
 */
export function MemberDirectory({ makerspaceId }: { makerspaceId: number }) {
  const [search, setSearch] = useState("");
  const [openId, setOpenId] = useState<number | null>(null);
  const directory = useQuery({
    queryKey: ["member", "directory", makerspaceId],
    queryFn: () => memberRequest<Directory>(`/member/makerspaces/${makerspaceId}/directory`),
    retry: false,
  });
  const detail = useQuery({
    queryKey: ["member", "directory", makerspaceId, openId],
    queryFn: () =>
      memberRequest<MemberProfile>(
        `/member/makerspaces/${makerspaceId}/directory/${openId}`,
      ),
    enabled: openId !== null,
    retry: false,
  });

  if (directory.isLoading) {
    return <section className="desk-panel p-5 text-sm text-muted">{t`Loading members…`}</section>;
  }
  if (directory.isError) return <section className="desk-panel p-5"><p role="alert" className="text-sm text-danger">{directory.error instanceof Error ? directory.error.message : t`Unable to load members.`}</p></section>;

  const entries = (directory.data?.members ?? []).filter(entry => `${entry.display_name} ${entry.headline}`.toLowerCase().includes(search.toLowerCase()));
  const hidden = directory.data?.hidden_count ?? 0;

  return (
    <section className="desk-panel p-5">
      <h2 className="title-panel">{t`Members`}</h2>
      <label className="mt-3 grid gap-1 text-sm sm:max-w-sm">{t`Search members`}<input className="desk-input" type="search" value={search} onChange={event => setSearch(event.target.value)} /></label>
      {detail.isLoading ? <p className="text-sm text-muted">{t`Loading profile…`}</p> : null}
      {detail.isError ? <p role="alert" className="text-sm text-danger">{detail.error instanceof Error ? detail.error.message : t`Unable to load this profile.`}</p> : null}
      {entries.length === 0 ? (
        <EmptyState message={search ? t`No members match. Try another name.` : t`No members have shared a profile yet.`} />
      ) : (
        <ul className="mt-3 space-y-2">
          {entries.map(entry => <li key={entry.membership_id}><ListRow title={entry.display_name}
            identity={entry.avatar_url ? { kind: "image", src: entry.avatar_url } : { kind: "avatar", name: entry.display_name, seed: String(entry.membership_id) }}
            meta={entry.headline} onClick={() => setOpenId(entry.membership_id)} /></li>)}
        </ul>
      )}
      {openId !== null ? <DetailDrawer open title={directory.data?.members.find(entry => entry.membership_id === openId)?.display_name || t`Member profile`} onClose={() => setOpenId(null)}>{detail.isLoading ? <p role="status">{t`Loading profile...`}</p> : detail.data ? <ProfileDetail profile={detail.data} /> : null}</DetailDrawer> : null}
      {hidden > 0 ? (
        <p className="mt-3 text-sm text-muted">
          {plural(hidden, { one: "# more member has not published a profile.", other: "# more members have not published a profile." })}
        </p>
      ) : null}
    </section>
  );
}

function ProfileDetail({ profile }: { profile: MemberProfile }) {
  return (
    <div className="desk-panel mt-2 border-brand p-3">
      {profile.institution ? (
        <p className="text-sm text-muted">{profile.institution}</p>
      ) : null}
      {profile.bio ? <p className="mt-2 text-sm text-ink">{profile.bio}</p> : null}
      <TagRow label={t`Interests`} values={profile.interests} />
      <TagRow label={t`Languages`} values={profile.languages} />
      {profile.education.length ? (
        <ul className="mt-3 space-y-2 text-sm text-muted">
          {profile.education.map((row, index) => {
            const tone = identityTone([row.qualification, row.institution, row.year].join("|"));
            return <li className={`border-l-2 ${tone.border} pl-3`} key={index}>
              {[row.qualification, row.institution, row.year].filter(Boolean).join(" · ")}
            </li>;
          })}
        </ul>
      ) : null}
      {profile.github_contributions !== null ? (
        <p className="mt-3 text-sm text-muted">
          <span className="tabular-nums">{profile.github_contributions}</span> {t` GitHub contributions in the last year.`}</p>
      ) : null}
      {typeof profile.activity?.events_attended === "number" ? (
        <p className="mt-1 text-sm text-muted">
          <span className="tabular-nums">{profile.activity.events_attended}</span> {t` events attended here.`}</p>
      ) : null}
      {profile.activity?.recent_attended_events?.length ? (
        <div className="mt-3">
          {/* "Recent" is load-bearing, not decoration: the backend caps this list, so a
              heading reading "Events attended" would claim to be the full history. The
              count above is the truthful total. */}
          <h3 className="title-section">{t`Recently attended`}</h3>
          <ul className="mt-1 space-y-1 text-sm text-muted">
            {profile.activity.recent_attended_events.map((event) => (
              <li key={event.id}>
                {event.title} ·{" "}
                <span className="tabular-nums">{new Date(event.starts_at).toLocaleDateString(formatLocale(), {
                  year: "numeric",
                  month: "short",
                  day: "numeric",
                })}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {profile.projects.length ? (
        <div className="mt-3 space-y-3">
          {profile.projects.map((project) => {
            const tone = identityTone(project.id);
            return <article key={project.id} className={`rounded-lg border ${tone.border} ${tone.surface} p-3`}>
              {project.image_url ? (
                <img
                  src={project.image_url}
                  alt=""
                  className="mb-2 max-h-40 w-full rounded-md object-cover"
                />
              ) : null}
              <h3 className="title-section">{project.title}</h3>
              {project.description ? (
                <p className="mt-1 text-sm text-muted">{project.description}</p>
              ) : null}
              {project.links.length ? (
                <ul className="mt-2 flex flex-wrap gap-3 text-sm">
                  {project.links.map((link, index) => {
                    const linkTone = identityTone(`${link.label}|${link.url}`);
                    return <li key={index}>
                      {/* External and member-authored: noopener/noreferrer keeps the
                          destination from reaching back through window.opener. */}
                      <a
                        className={`${linkTone.ink} inline-flex min-h-11 items-center break-all underline`}
                        href={link.url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {link.label}
                      </a>
                    </li>;
                  })}
                </ul>
              ) : null}
            </article>;
          })}
        </div>
      ) : null}
    </div>
  );
}

function TagRow({ label, values }: { label: string; values: string[] }) {
  if (!values.length) return null;
  return (
    <p className="mt-2 text-sm text-muted">
      <span className="eyebrow text-ink">{label}:</span> {values.join(", ")}
    </p>
  );
}

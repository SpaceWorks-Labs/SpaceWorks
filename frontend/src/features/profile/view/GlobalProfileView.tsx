import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Pencil, Share2 } from "lucide-react";
import { PageMetadata } from "../../../components/PageMetadata";
import { Avatar } from "../../../components/ui";
import { RouteLink } from "../../../components/ui/RouteLink";
import type { AccountProfile, SectionKey } from "../accountProfileTypes";
import { ResumeBlocks } from "./ResumeBlocks";

/** What another signed-in member would see: every section whose switch is off is dropped (the server does the same). */
export function asVisitor(profile: AccountProfile): AccountProfile {
  const off = (key: SectionKey) => !profile.shown[key];
  return {
    ...profile, audience: "member",
    status: off("status") ? null : profile.status, bio: off("about") ? "" : profile.bio,
    timeline: profile.timeline.filter(row => row.kind === "education" ? !off("education") : !off("experience")),
    education: off("education") ? [] : profile.education,
    skills: off("skills") ? [] : profile.skills, domains: off("skills") ? [] : profile.domains,
    links: off("links") ? [] : profile.links, interests: off("interests") ? [] : profile.interests, languages: off("interests") ? [] : profile.languages,
    projects: off("projects") ? [] : profile.projects.filter(project => project.public_visible),
    achievements: off("achievements") ? { verified: [], self_reported: [] } : profile.achievements,
    events_attended: off("events") ? null : profile.events_attended,
    certifications: off("certifications") ? [] : profile.certifications,
    spaces: off("spaces") ? [] : profile.spaces, organizations: off("spaces") ? [] : profile.organizations,
  };
}

/** The open web means the profile is reachable by logged-out visitors: they are served only when `public_visible`. */
export const isOpenWeb = (profile: AccountProfile) => profile.audience === "public" || profile.audience === "owner" && Boolean(profile.public_visible);

function ShareButton({ profile }: { profile: AccountProfile }) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");
  const share = async () => {
    const url = `${window.location.origin}/${profile.handle}`;
    try {
      if (typeof navigator.share === "function") await navigator.share({ title: profile.display_name, url });
      else { await navigator.clipboard.writeText(url); setState("copied"); }
    } catch (error) { setState(error instanceof DOMException && error.name === "AbortError" ? "idle" : "failed"); }
  };
  return <>
    <button type="button" className="desk-button gap-2" onClick={() => { void share(); }}><Share2 aria-hidden="true" className="h-4 w-4" />{t`Share`}</button>
    <p role="status" className="basis-full text-sm text-muted">{state === "copied" ? t`Link copied.` : state === "failed" ? t`Couldn't share the link. Copy it from the address bar.` : ""}</p>
  </>;
}

/**
 * Résumé-style profile for any audience. The body is whatever the server sent for that audience; the share card,
 * share button and meta tags exist only for open-web profiles.
 */
export function GlobalProfileView({ profile, editHref, preview = false }: { profile: AccountProfile; editHref?: string; preview?: boolean }) {
  const Heading = preview ? "h2" : "h1";
  const open = !preview && Boolean(profile.handle) && isOpenWeb(profile);
  const description = profile.headline || profile.bio.slice(0, 160) || t`Profile on Space Works`;
  return <article className="grid min-w-0 gap-6">
    {open ? <PageMetadata title={profile.display_name} description={description} path={`/${profile.handle}`} image={profile.avatar_url} imageAlt={profile.display_name} /> : null}
    <header className="grid gap-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        {profile.avatar_url ? <img src={profile.avatar_url} alt="" className="h-24 w-24 rounded-full border border-line object-cover" />
          : <span className="inline-flex h-24 w-24 items-center justify-center [&>span]:h-24 [&>span]:w-24 [&>span]:text-2xl">
            <Avatar name={profile.display_name} seed={profile.handle ?? String(profile.account_id)} size="lg" /></span>}
        {preview ? null : <div className="flex flex-wrap items-center gap-2">
          {editHref ? <RouteLink href={editHref} className="desk-button gap-2"><Pencil aria-hidden="true" className="h-4 w-4" />{t`Edit profile`}</RouteLink> : null}
          {open ? <ShareButton profile={profile} /> : null}
        </div>}
      </div>
      <div className="grid gap-2">
        {profile.handle ? <span className="chip w-fit">@{profile.handle}</span> : null}
        <Heading className="font-accent break-words text-ink">{profile.display_name}</Heading>
        {profile.headline ? <p className="text-lg text-ink">{profile.headline}</p> : null}
        {profile.institution ? <p className="text-muted">{profile.institution}</p> : null}
      </div>
    </header>
    <ResumeBlocks profile={profile} />
  </article>;
}

import { useState } from "react";
import { ArrowUpRight, BadgeCheck, Pencil, Share2 } from "lucide-react";
import { Avatar } from "../../components/ui";
import { RouteLink } from "../../components/ui/RouteLink";
import { plural } from "../../lib/plural";
import { domainIcon, linkPresentation } from "./profileFormat";
import type { PublicProfile } from "./publicProfileApi";

async function shareProfile(name: string, url: string) {
  if (typeof navigator.share === "function") {
    await navigator.share({ title: name, url });
    return "shared" as const;
  }
  await navigator.clipboard.writeText(url);
  return "copied" as const;
}

function VouchLine({ profile }: { profile: PublicProfile }) {
  if (!profile.vouched_by.length && !profile.vouched_count) return null;
  return <p className="text-sm text-muted">
    {profile.vouched_by.length ? <>Vouched by{" "}{profile.vouched_by.map((voucher, index) => <span key={voucher.handle}>
      {index ? ", " : ""}<RouteLink href={`/${voucher.handle}`} className="inline-flex items-center gap-0.5 font-semibold text-ink underline-offset-2 hover:underline">
        {voucher.display_name}<ArrowUpRight aria-hidden="true" className="h-3.5 w-3.5" /></RouteLink>
    </span>)}</> : null}
    {profile.vouched_by.length && profile.vouched_count ? " · " : null}
    {profile.vouched_count ? <>Vouched for <span className="font-semibold text-ink">{plural(profile.vouched_count, "maker")}</span></> : null}
  </p>;
}

/** The page's one h1 (h2 inside the editor preview) and its only Unbounded accent: the display name. */
export function ProfileHeader({ profile, editHref, preview = false }: {
  profile: PublicProfile; editHref?: string; preview?: boolean;
}) {
  const Heading = preview ? "h2" : "h1";
  const [shareState, setShareState] = useState<"idle" | "copied" | "failed">("idle");
  const share = () => {
    const url = `${window.location.origin}/${profile.handle}`;
    shareProfile(profile.display_name, url).then(result => setShareState(result === "copied" ? "copied" : "idle"))
      .catch((error: unknown) => setShareState(error instanceof DOMException && error.name === "AbortError" ? "idle" : "failed"));
  };
  return <header className="grid gap-5">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="relative shrink-0">
        {profile.avatar_url ? <img src={profile.avatar_url} alt="" className="h-24 w-24 rounded-full border border-line object-cover" />
          : <span className="inline-flex h-24 w-24 items-center justify-center [&>span]:h-24 [&>span]:w-24 [&>span]:text-2xl"><Avatar name={profile.display_name} seed={profile.handle} size="lg" /></span>}
        {profile.verified ? <span role="img" aria-label="Verified member" title="Verified member"
          className="absolute -right-1 bottom-1 inline-flex rounded-full bg-panel text-info"><BadgeCheck aria-hidden="true" className="h-7 w-7" /></span> : null}
      </div>
      {preview ? null : <div className="flex flex-wrap gap-2">
        {editHref ? <RouteLink href={editHref} className="desk-button gap-2"><Pencil aria-hidden="true" className="h-4 w-4" />Edit profile</RouteLink> : null}
        <button type="button" className="desk-button gap-2" onClick={share}><Share2 aria-hidden="true" className="h-4 w-4" />Share</button>
      </div>}
    </div>
    <div className="grid gap-2">
      <span className="chip w-fit">@{profile.handle}</span>
      <Heading className="font-accent break-words text-ink">{profile.display_name}</Heading>
      {profile.headline ? <p className="text-lg text-ink">{profile.headline}</p> : null}
      {profile.institution ? <p className="text-muted">{profile.institution}</p> : null}
      {profile.bio ? <p className="max-w-prose whitespace-pre-line break-words text-ink">{profile.bio}</p> : null}
      <p role="status" className="text-sm text-muted">{shareState === "copied" ? "Link copied." : shareState === "failed" ? "Couldn't share the link. Copy it from the address bar." : ""}</p>
    </div>
    {profile.domains.length ? <ul aria-label="Domains" className="flex flex-wrap gap-2">
      {profile.domains.map(domain => { const Glyph = domainIcon(domain); return <li key={domain}
        className="inline-flex min-h-9 items-center gap-2 rounded-full border border-line bg-surface px-3 text-sm font-semibold uppercase tracking-[0.04em] text-ink">
        <Glyph aria-hidden="true" className="h-4 w-4 text-brand-ink" />{domain}</li>; })}
    </ul> : null}
    {profile.links.length ? <ul aria-label="Links" className="flex flex-wrap gap-2">
      {profile.links.map(link => { const { label, Icon } = linkPresentation(link); return <li key={link.url}>
        <a href={link.url} target="_blank" rel="noopener noreferrer nofollow ugc" aria-label={`${label} (opens in a new tab)`} title={label}
          className="desk-button min-h-11 min-w-11 gap-2 rounded-full px-3"><Icon aria-hidden="true" className="h-4 w-4" /><span className="text-sm">{label}</span></a>
      </li>; })}
    </ul> : null}
    <VouchLine profile={profile} />
  </header>;
}

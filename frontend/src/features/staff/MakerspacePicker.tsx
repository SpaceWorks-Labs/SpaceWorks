import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { SpaceWorksBadge } from "../../components/SpaceWorksLogo";
import { ThemeToggle } from "../../components/ThemeToggle";
import { ListRow } from "../../components/ui";
import { DashboardLayout } from "../../components/layouts/DashboardLayout";
import { consoleSessionHref } from "../../lib/api/sessionContext";
import type { Makerspace } from "./StaffPanels";
import { nounOf, spaceKindOf } from "../../lib/spaceNoun";

/**
 * Superadmin entry screen: the superadmin operates one makerspace at a time, so
 * before the console loads they explicitly pick which makerspace to operate. The
 * chosen id then scopes every staff API call (the backend already takes a
 * makerspace_id per request). Reachable again via "Switch makerspace" in the shell.
 */
export function MakerspacePicker({
  makerspaces,
  loading,
  username,
  onSelect,
  onSignOut,
  person = false,
}: {
  /** A person with staff roles in several spaces (one account per person) rather than the superadmin. */
  person?: boolean;
  makerspaces: Makerspace[];
  loading: boolean;
  username: string;
  onSelect: (id: number) => void;
  onSignOut: () => void;
}) {
  const [search, setSearch] = useState("");
  const now = new Date();
  const today = now.toLocaleDateString(formatLocale(), { weekday: "long", day: "numeric", month: "long" });
  const greeting = now.getHours() < 12 ? t`Good morning` : now.getHours() < 18 ? t`Good afternoon` : t`Good evening`;
  // Decision 295: once organization workspaces are in the list, the wording turns neutral ("space").
  const mixed = makerspaces.some(space => spaceKindOf(space) === "organization");
  const matches = makerspaces.filter(space => `${space.name} ${space.public_code} ${space.slug}`.toLocaleLowerCase().includes(search.toLocaleLowerCase()));
  return <DashboardLayout standalone
    state={{ status: loading ? "loading" : "ready" }}
    header={{ eyebrow: person ? t`${greeting}, ${username} · ${today}` : t`Super Admin · ${greeting}, ${username} · ${today}`, title: mixed ? (person ? t`Choose a space` : t`Choose a space to operate`) : person ? t`Choose a makerspace` : t`Choose a makerspace to operate`,
      subtitle: t`Choose a space to work in.`,
      meta: <div className="flex items-center gap-3"><SpaceWorksBadge /><ThemeToggle /></div>,
      // The superadmin's platform pages (Overview, Spaces, People & access, Security, Data) need no space.
      primary: person ? undefined : { label: t`Open the platform console`, href: consoleSessionHref("/admin/platform-dashboard", "platform") },
      secondary: { label: t`Sign out`, onClick: onSignOut } }}
    stats={[]} progress={<label className="grid gap-2 text-sm font-semibold">{mixed ? t`Find a space` : t`Find a makerspace`}<input className="desk-input" aria-label={t`Name, code or slug`} placeholder={t`Name, code or slug`} value={search} onChange={event => setSearch(event.target.value)} /></label>}
    main={[{ title: mixed ? t`Your spaces` : t`Your makerspaces`, isEmpty: !matches.length, empty: { message: makerspaces.length ? t`No spaces match. Try another name, code or slug.` : person ? t`You don't hold a staff role in any makerspace yet.` : t`No makerspaces exist yet. Create one on the platform console's Spaces page.`, action: makerspaces.length || person ? undefined : { label: t`Create a makerspace`, href: consoleSessionHref("/admin/platform-spaces", "platform") } }, content: <div className="grid gap-3 sm:grid-cols-2">{matches.map(space => <ListRow key={space.id} title={space.name}
      identity={{ kind: "icon", icon: "Building2", tone: "accent" }}
      meta={<SpaceRowMeta space={space} />}
      onClick={() => onSelect(space.id)} />)}</div> }]} />;
}

function SpaceRowMeta({ space }: { space: Makerspace }) {
  const code = space.public_code ?? space.slug;
  const noun = nounOf(space);
  return <>{t`${code} · Operate this ${noun} →`}</>;
}

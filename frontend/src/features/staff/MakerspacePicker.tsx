import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { SpaceWorksBadge } from "../../components/SpaceWorksLogo";
import { ThemeToggle } from "../../components/ThemeToggle";
import { ListRow } from "../../components/ui";
import { DashboardLayout } from "../../components/layouts/DashboardLayout";
import { configuredApiUrl } from "../../lib/runtimeConfig";
import type { Makerspace } from "./StaffPanels";

/** `/control/` is Django, served by the API origin: an absolute URL forces a real page load
 * instead of a client-side route that would land on the SPA's not-found page. */
function controlPlaneUrl() {
  try { return `${new URL(configuredApiUrl(), window.location.origin).origin}/control/`; } catch { return "/control/"; }
}

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
  const greeting = now.getHours() < 12 ? "Good morning" : now.getHours() < 18 ? "Good afternoon" : "Good evening";
  const matches = makerspaces.filter(space => `${space.name} ${space.public_code} ${space.slug}`.toLocaleLowerCase().includes(search.toLocaleLowerCase()));
  return <DashboardLayout standalone
    state={{ status: loading ? "loading" : "ready" }}
    header={{ eyebrow: `${person ? "" : "Super Admin · "}${greeting}, ${username} · ${now.toLocaleDateString(formatLocale(), { weekday: "long", day: "numeric", month: "long" })}`, title: person ? t`Choose a makerspace` : t`Choose a makerspace to operate`,
      subtitle: t`Choose a space to work in.`,
      meta: <div className="flex items-center gap-3"><SpaceWorksBadge /><ThemeToggle /></div>,
      secondary: { label: t`Sign out`, onClick: onSignOut } }}
    stats={[]} progress={<label className="grid gap-2 text-sm font-semibold">{t`Find a makerspace`}<input className="desk-input" aria-label={t`Name, code or slug`} placeholder={t`Name, code or slug`} value={search} onChange={event => setSearch(event.target.value)} /></label>}
    main={[{ title: t`Your makerspaces`, isEmpty: !matches.length, empty: { message: makerspaces.length ? t`No spaces match. Try another name, code or slug.` : person ? t`You don't hold a staff role in any makerspace yet.` : t`No makerspaces exist yet. Create one from the Django control plane.`, action: makerspaces.length || person ? undefined : { label: t`Open control plane`, href: controlPlaneUrl() } }, content: <div className="grid gap-3 sm:grid-cols-2">{matches.map(space => <ListRow key={space.id} title={space.name}
      identity={{ kind: "icon", icon: "Building2", tone: "accent" }}
      meta={<>{t`${space.public_code ?? space.slug} · Operate this makerspace →`}</>}
      onClick={() => onSelect(space.id)} />)}</div> }]} />;
}

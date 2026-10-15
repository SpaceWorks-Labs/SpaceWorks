import { useState } from "react";
import { SpaceWorksBadge } from "../../components/SpaceWorksLogo";
import { ThemeToggle } from "../../components/ThemeToggle";
import { ListRow, StatusPill } from "../../components/ui";
import { DashboardLayout } from "../../components/layouts/DashboardLayout";
import type { Makerspace } from "./StaffPanels";

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
}: {
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
    header={{ eyebrow: `${greeting}, ${username} · ${now.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" })}`, title: "Choose a makerspace to operate",
      subtitle: "Choose a space to work in.",
      meta: <div className="flex items-center gap-3"><SpaceWorksBadge /><ThemeToggle /></div>,
      secondary: { label: "Sign out", onClick: onSignOut } }}
    stats={[]} progress={<label className="grid gap-2 text-sm font-semibold">Find a makerspace<input className="desk-input" aria-label="Name, code or slug" placeholder="Name, code or slug" value={search} onChange={event => setSearch(event.target.value)} /></label>}
    main={[{ title: "Your makerspaces", isEmpty: !matches.length, empty: { message: makerspaces.length ? "No spaces match. Try another name, code or slug." : "No spaces yet. Create one from Staff & roles or the control plane.", action: makerspaces.length ? undefined : { label: "Open control plane", href: "/control/" } }, content: <div className="grid gap-3 sm:grid-cols-2">{matches.map(space => <ListRow key={space.id} title={space.name}
      identity={{ kind: "icon", icon: "Building2", tone: "accent" }}
      meta={<>{space.public_code ?? space.slug} · Operate this makerspace →</>}
      onClick={() => onSelect(space.id)}
      right={space.superadmin_access_enabled === false ? <StatusPill tone="warn" label="Superadmin access: Off" /> : null} />)}</div> }]} />;
}

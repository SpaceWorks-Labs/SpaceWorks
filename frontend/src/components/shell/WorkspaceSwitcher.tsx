import { useState } from "react";
import { ChevronsUpDown } from "lucide-react";
import { ActionControl, IdentityChip } from "../ui";
import { Disclosure } from "./Disclosure";
import type { ShellWorkspace } from "./types";

export function WorkspaceSwitcher({ workspace }: { workspace?: ShellWorkspace }) {
  const [search, setSearch] = useState("");
  const label = <>{workspace ? <IdentityChip identity={workspace.avatar} label={workspace.name} /> : null}
    <span className="min-w-0 flex-1"><span className="block truncate text-sm font-semibold">{workspace?.name ?? "Choose a space"}</span>{" "}
      {workspace?.subtitle ? <span className="block truncate text-xs text-muted">{workspace.subtitle}</span> : null}</span></>;
  if (!workspace?.menu?.length || workspace.locked) return <div className="flex min-h-14 items-center gap-2 rounded-xl border border-line bg-panel p-2">{label}</div>;
  return <Disclosure label={<>{label}<ChevronsUpDown aria-hidden="true" size={24} /></>}>
    {workspace.menu.length > 6 ? <input aria-label="Find a makerspace" className="desk-input mb-2 w-full" value={search} onChange={event => setSearch(event.target.value)} /> : null}
    {workspace.menu.filter(action => !search || action.label.toLowerCase().includes(search.toLowerCase())).map(action => <ActionControl key={action.label} action={action} className="w-full justify-start" />)}
  </Disclosure>;
}

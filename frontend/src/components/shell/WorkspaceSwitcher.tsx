import { t } from "@lingui/core/macro";
import { useState } from "react";
import { ChevronsUpDown } from "lucide-react";
import { ActionControl, IdentityChip } from "../ui";
import { Disclosure } from "./Disclosure";
import type { ShellWorkspace } from "./types";
import { SearchField } from "../ui/SearchField";

export function WorkspaceSwitcher({ workspace }: { workspace?: ShellWorkspace }) {
  const [search, setSearch] = useState("");
  const label = <>{workspace ? <IdentityChip identity={workspace.avatar} label={workspace.name} /> : null}
    <span className="min-w-0 flex-1"><span className="block truncate text-sm font-semibold">{workspace?.name ?? t`Choose a makerspace`}</span>{" "}
      {workspace?.subtitle ? <span className="block truncate text-xs text-muted">{workspace.subtitle}</span> : null}</span></>;
  if (!workspace?.menu?.length || workspace.locked) return <div className="flex min-h-14 items-center gap-2 rounded-xl border border-line bg-panel p-2">{label}</div>;
  const matches = workspace.menu.filter(action => !search || action.label.toLowerCase().includes(search.toLowerCase()));
  return <Disclosure label={<>{label}<ChevronsUpDown aria-hidden="true" size={24} /></>}>
    {workspace.menu.length > 6 ? <SearchField aria-label={t`Find a makerspace`} className="desk-input mb-2 w-full" value={search} onChange={event => setSearch(event.target.value)} /> : null}
    {matches.map(action => <ActionControl key={action.label} action={action} className="w-full justify-start" />)}
    {search && !matches.length ? <p role="status" className="px-2 py-1 text-sm text-muted">{t`No makerspace matches.`}</p> : null}
  </Disclosure>;
}

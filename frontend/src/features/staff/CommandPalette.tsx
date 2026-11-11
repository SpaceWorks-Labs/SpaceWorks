import { t } from "@lingui/core/macro";
import { consoleSessionHref } from "../../lib/api/sessionContext";
import { useEffect, useId, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { Modal } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import { useDebouncedValue } from "../../lib/useDebouncedValue";
import { TAB_LABELS } from "./staffAccess";
import { staffTabPath } from "./staffTabs";
import { SIDEBAR_LABELS } from "./sidebarSections";
import { quickCreateCommands } from "./quickCreate";
import { reportCommands } from "./reportCommands";

type Hit = { entity: string; id: number; label: string; tab: string; query: Record<string, string> };
type Command = { key: string; label: string; tab: string; query?: Record<string, string> };
// Decision 242 (U6): the server adds machine jobs, shop orders, payments, incidents and guest passes, each only
// for a role holding that area's action. A hit opens its area's page, so it is named by what it is.
const ENTITY_LABELS = (): Record<string, string> => ({ jobs: t`Machine job`, shop: t`Shop order`, payments: t`Payment`,
  incidents: t`Incident`, passes: t`Guest pass` });
const hitCommand = (hit: Hit): Command => {
  const link = { tab: hit.tab, filters: hit.query ?? {} };
  const kind = ENTITY_LABELS()[hit.entity] ?? TAB_LABELS[link.tab] ?? hit.entity;
  return { key: `${hit.entity}-${hit.id}`, label: hit.label.startsWith(kind) ? hit.label : `${kind}: ${hit.label}`, tab: link.tab, query: link.filters };
};

export function CommandPalette({ makerspaceId, makerspaceSlug, allowedTabs, guestOnly, singleTenantLocked, ownerName, actions = [], isSuperadmin = false, open: controlledOpen, onOpenChange }: {
  makerspaceId: number; makerspaceSlug: string; allowedTabs: readonly string[]; guestOnly: boolean; singleTenantLocked: boolean; ownerName: string;
  actions?: readonly string[]; isSuperadmin?: boolean; open?: boolean; onOpenChange?: (open: boolean) => void;
}) {
  const navigate = useNavigate();
  const id = useId();
  const [localOpen, setLocalOpen] = useState(false);
  const open = controlledOpen ?? localOpen;
  const setOpen = (next: boolean) => { setLocalOpen(next); onOpenChange?.(next); };
  const [search, setSearch] = useState("");
  const [active, setActive] = useState(0);
  const term = useDebouncedValue(search, 250).trim();
  const results = useQuery({
    queryKey: ["staff-search", ownerName, makerspaceId, term],
    queryFn: ({ signal }) => staffRequest<{ results: Hit[] }>(`/admin/search?makerspace_id=${makerspaceId}&q=${encodeURIComponent(term)}`, { signal }),
    enabled: open && term.length >= 2,
    staleTime: 0,
  });
  // Match the old tab name and the sidebar's name ("Inbox", "Home", "Pickups (Handover)") so either finds the page.
  const needle = search.toLowerCase().trim();
  const commands: Command[] = allowedTabs.filter((tab) => [TAB_LABELS[tab] ?? tab, SIDEBAR_LABELS[tab]].some(name => name?.toLowerCase().includes(needle)))
    .map((tab) => ({ key: `tab-${tab}`, label: t`Go to ${TAB_LABELS[tab] ?? tab}`, tab }));
  commands.push(...quickCreateCommands(actions, allowedTabs, isSuperadmin).filter(command => command.label.toLowerCase().includes(search.toLowerCase().trim())));
  // Reports are listed only once something is typed, so the empty palette stays a short list of pages.
  if (needle) commands.push(...reportCommands(actions, allowedTabs, isSuperadmin).filter(command => command.label.toLowerCase().includes(needle)));
  if (term === search.trim() && term.length >= 2) results.data?.results.map(hitCommand).filter((command) => allowedTabs.includes(command.tab)).forEach((command) => commands.push(command));
  const current = Math.min(active, Math.max(0, commands.length - 1));
  useEffect(() => {
    if (open) document.getElementById(`${id}-option-${current}`)?.scrollIntoView?.({ block: "nearest" });
  }, [open, id, current, commands.length]);

  const close = () => { setOpen(false); setSearch(""); setActive(0); };
  useEffect(() => {
    const keydown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        // Keep the existing dialog stack intact when evidence/action dialogs own focus.
        if (!open && document.querySelector('[role="dialog"]')) return;
        setOpen(!open); setSearch(""); setActive(0);
      }
    };
    document.addEventListener("keydown", keydown);
    return () => document.removeEventListener("keydown", keydown);
  }, [open]);
  useEffect(() => { setOpen(false); setSearch(""); setActive(0); }, [makerspaceId, ownerName]);

  const run = (command?: Command) => {
    if (!command) return;
    const path = staffTabPath(command.tab, guestOnly, isSuperadmin ? undefined : makerspaceSlug, singleTenantLocked);
    const query = command.query ? new URLSearchParams(command.query).toString() : "";
    close();
    navigate(consoleSessionHref(path + (query ? `?${query}` : "")));
  };
  return <>
    {controlledOpen === undefined ? <button type="button" className="desk-button-ghost ml-5" onClick={() => setOpen(true)} aria-haspopup="dialog">{t`Search and commands `}<kbd>{t`Ctrl/⌘ K`}</kbd></button> : null}
    {open ? <Modal open onClose={close} title={t`Search and commands`}>
      <label htmlFor={`${id}-input`} className="sr-only">{t`Search staff console`}</label>
      <input id={`${id}-input`} className="desk-input w-full" role="combobox" aria-autocomplete="list" aria-expanded="true" aria-controls={`${id}-list`} aria-activedescendant={commands.length ? `${id}-option-${current}` : undefined}
        value={search} maxLength={100} onChange={(event) => { setSearch(event.target.value); setActive(0); }}
        onKeyDown={(event) => {
          if (["ArrowDown", "ArrowUp", "Home", "End", "Enter"].includes(event.key)) event.preventDefault();
          if (event.key === "ArrowDown") setActive(commands.length ? (current + 1) % commands.length : 0);
          if (event.key === "ArrowUp") setActive(commands.length ? (current + commands.length - 1) % commands.length : 0);
          if (event.key === "Home") setActive(0);
          if (event.key === "End") setActive(Math.max(0, commands.length - 1));
          if (event.key === "Enter") run(commands[current]);
        }} />
      <div role="status" aria-live="polite" className="my-2 text-xs text-muted">{results.isFetching ? t`Searching…` : t`${commands.length} commands and results`}</div>
      {results.error && term.length >= 2 ? <p role="alert" className="text-sm text-danger">{t`Search unavailable: ${results.error.message}`}</p> : null}
      <ul id={`${id}-list`} role="listbox" aria-label={t`Commands and results`} className="max-h-80 overflow-y-auto">
        {commands.map((command, index) => <li key={command.key} id={`${id}-option-${index}`} role="option" aria-selected={index === current}
          className={`cursor-pointer rounded p-3 ${index === current ? "bg-surface font-semibold" : ""}`}
          onMouseDown={(event) => event.preventDefault()} onClick={() => run(command)}>{command.label}</li>)}
      </ul>
      {!commands.length && !results.isFetching ? <p className="text-sm text-muted">{t`No matching commands or results.`}</p> : null}
    </Modal> : null}
  </>;
}

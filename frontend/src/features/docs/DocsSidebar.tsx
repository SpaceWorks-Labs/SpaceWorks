import { t } from "@lingui/core/macro";
import { ChevronRight } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { API_REFERENCE_PATH, docGroups, groupLabel } from "./docsIndex";
import type { DocEntry } from "./docsTypes";

type NavLink = { key: string; title: string; to: string };

function sidebarGroups(source?: readonly DocEntry[]) {
  const groups = docGroups(source).map(group => ({ name: group.name,
    links: group.pages.map((page): NavLink => ({ key: page.id, title: page.title, to: `/docs/${page.id}` })) }));
  const reference: NavLink = { key: "api/reference", title: t`API reference`, to: API_REFERENCE_PATH };
  const api = groups.find(group => group.name === "API");
  if (api) api.links.unshift(reference);
  else groups.splice(Math.max(0, groups.findIndex(group => group.name === "Reference")), 0, { name: "API", links: [reference] });
  return groups;
}

/** Grouped navigation; a group opens when it holds the current page and stays as the reader leaves it. */
export function DocsSidebar({ currentId, onNavigate, source }: { currentId: string; onNavigate?: () => void; source?: readonly DocEntry[] }) {
  const groups = sidebarGroups(source);
  const isCurrent = (link: NavLink) => link.key === "api/reference" ? currentId.startsWith("api/reference") : link.key === currentId;
  const holder = groups.find(group => group.links.some(isCurrent))?.name;
  const [open, setOpen] = useState<Record<string, boolean>>(() => (holder ? { [holder]: true } : {}));
  useEffect(() => { if (holder) setOpen(state => state[holder] ? state : { ...state, [holder]: true }); }, [holder]);
  return <nav aria-label={t`Documentation`} className="sw-doc-nav">
    <Link to="/docs" className="sw-doc-nav-home" aria-current={currentId === "" ? "page" : undefined} onClick={onNavigate}>{t`Overview`}</Link>
    {groups.map(group => {
      const expanded = Boolean(open[group.name]);
      const listId = `docs-nav-${group.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
      return <div key={group.name} className="sw-doc-nav-group">
        <button type="button" className="sw-doc-nav-toggle" aria-expanded={expanded} aria-controls={listId}
          onClick={() => setOpen(state => ({ ...state, [group.name]: !expanded }))}>
          <ChevronRight size={16} aria-hidden="true" className="sw-doc-nav-chevron" />
          <span className="min-w-0 flex-1 text-left">{groupLabel(group.name)}</span>
          <span className="text-xs font-medium text-muted tabular-nums">{group.links.length}</span>
        </button>
        <ul id={listId} hidden={!expanded}>
          {group.links.map(link => <li key={link.key}>
            <Link to={link.to} aria-current={isCurrent(link) ? "page" : undefined} className="sw-doc-nav-link" onClick={onNavigate}>{link.title}</Link>
          </li>)}
        </ul>
      </div>;
    })}
  </nav>;
}

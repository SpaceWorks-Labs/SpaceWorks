import { t } from "@lingui/core/macro";
import { ArrowUpRight } from "lucide-react";
import { Link } from "react-router-dom";
import { useTransitionNavigate } from "../../lib/motion";
import { useState, type MouseEvent } from "react";

import { useLayoutMedia } from "../../components/layouts/useLayoutMedia";
import { settingsGroups, type SettingsGroup } from "./settingsSections";

type Props = {
  /** Section id → title, for the sections this actor and space have. */
  titles: Readonly<Record<string, string>>;
  /** `tab:<tab>[/<view>]` menu entry → its title and href, for the console pages this actor may open. */
  links?: Readonly<Record<string, { title: string; href: string }>>;
  active: string;
  href: (section: string) => string;
  /** False cancels the move (an editor on the current page holds unsaved changes). */
  canLeave: () => boolean;
  /** The menu's groups; the space settings groups unless a page (platform settings) has its own. */
  groups?: readonly SettingsGroup[];
  /** One line of help per entry: when given, a filter box searches titles and help (decision 255). */
  help?: Readonly<Record<string, string>>;
};

const itemClass = "flex min-h-11 shrink-0 items-center gap-2 rounded-control px-3 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus";

/**
 * Routed settings navigation: a grouped link rail from tablet up and one native select on
 * phones. Every entry is a real URL, so each subpage is deep-linkable and the browser back
 * button walks the pages the person visited. Entries that open another console page carry
 * an arrow, so leaving Settings is never a surprise.
 */
export function SettingsSectionNav({ titles, links = {}, active, href, canLeave, groups: source = settingsGroups(), help }: Props) {
  const phone = useLayoutMedia("(max-width: 767px)");
  const navigate = useTransitionNavigate();
  const [query, setQuery] = useState("");
  const words = phone ? [] : query.toLowerCase().split(/\s+/).filter(Boolean);
  const matches = (id: string) => {
    const text = `${titles[id] ?? links[id]?.title ?? ""} ${help?.[id] ?? ""}`.toLowerCase();
    return words.every(word => text.includes(word));
  };
  const groups = source.map(group => ({ ...group, items: group.items.filter(id => (id in titles || id in links) && matches(id)) }))
    .filter(group => group.items.length);
  const target = (id: string) => links[id]?.href ?? href(id);
  if (phone) return <nav aria-label={t`Settings pages`} className="sw-settings-nav min-w-0">
    <label className="grid gap-2"><span className="text-sm font-semibold text-ink">{t`Settings page`}</span>
      <select className="desk-input w-full" value={active} onChange={event => {
        if (event.target.value !== active && canLeave()) navigate(target(event.target.value));
      }}>
        {groups.map(group => <optgroup key={group.key} label={group.label}>
          {group.items.map(id => <option key={id} value={id}>{titles[id] ?? t`${links[id].title} (own page)`}</option>)}
        </optgroup>)}
      </select>
    </label>
  </nav>;
  const guard = (id: string) => (event: MouseEvent) => { if (id !== active && !canLeave()) event.preventDefault(); };
  return <nav aria-label={t`Settings pages`} className="sw-settings-nav grid min-w-0 content-start gap-4 pb-2">
    {help ? <div role="search" className="grid min-w-0 gap-1 px-1"><label className="sr-only" htmlFor="settings-nav-filter">{t`Search settings`}</label>
      <input id="settings-nav-filter" type="search" className="desk-input w-full" value={query} placeholder={t`Search settings`}
        onChange={event => setQuery(event.target.value)} />
      {words.length && !groups.length ? <p role="status" className="px-2 text-sm text-muted">{t`No settings match. Try another word.`}</p> : null}
    </div> : null}
    {groups.map(group => <div key={group.key} className="grid min-w-0 gap-1">
      <p aria-hidden="true" className="px-3 text-xs font-semibold uppercase tracking-wide text-muted">{group.label}</p>
      <ul aria-label={group.label} className="flex min-w-0 flex-wrap gap-1 xl:grid">{group.items.map(id => <li key={id} className="min-w-0">
        {id in titles ? <Link to={href(id)} onClick={guard(id)} aria-current={id === active ? "page" : undefined}
          className={`${itemClass} ${id === active ? "bg-hover text-ink" : "text-muted hover:bg-hover hover:text-ink"}`}>
          {titles[id]}</Link>
          : <Link to={links[id].href} onClick={guard(id)} className={`${itemClass} text-muted hover:bg-hover hover:text-ink`}>
            <span className="min-w-0">{links[id].title}</span>
            <ArrowUpRight aria-hidden="true" size={14} className="shrink-0" /><span className="sr-only">{t`(opens its own page)`}</span></Link>}
      </li>)}</ul>
    </div>)}
  </nav>;
}

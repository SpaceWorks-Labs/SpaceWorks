import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, Circle, Users } from "lucide-react";

import { ProgressBar } from "../../components/ui";
import { useChannels } from "../notifications/channelsApi";
import type { Makerspace } from "./panels/shared";
import { hubEntries, searchHub, setupChecklist, type HubEntry, type HubTarget } from "./settingsHubCatalog";

type Props = { makerspace: Makerspace; sectionIds: readonly string[]; allowedTabs: readonly string[];
  tabHref: (tab: string) => string };

const linkClass = "flex min-h-11 min-w-0 items-center gap-3 rounded-lg px-3 py-2 text-sm hover:bg-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus";

function jump(section: string) {
  const target = document.getElementById(section);
  target?.scrollIntoView?.({ block: "start" });
  target?.focus({ preventScroll: true });
}

function Destination({ target, tabHref, children }: { target: HubTarget; tabHref: Props["tabHref"]; children: ReactNode }) {
  if ("tab" in target) return <Link className={linkClass} to={tabHref(target.tab)}>{children}</Link>;
  return <a className={linkClass} href={`#${target.section}`} onClick={event => { event.preventDefault(); jump(target.section); }}>{children}</a>;
}

/**
 * The top of the Settings page: one search over every setting (on this page and on the
 * settings pages beside it), the setup checklist, and Staff & roles, which a Space Manager
 * needs more often than any switch.
 */
export function SettingsHub({ makerspace, sectionIds, allowedTabs, tabHref }: Props) {
  const [query, setQuery] = useState("");
  const notifications = (makerspace.enabled_modules ?? []).includes("notifications") && sectionIds.includes("channels");
  const channels = useChannels(makerspace.id, notifications);
  const entries = hubEntries(sectionIds, allowedTabs);
  const results = searchHub(entries, query);
  const checklist = setupChecklist(makerspace, { channelsReady: notifications && channels.data
    ? channels.data.results.some(row => row.enabled) : undefined });
  const done = checklist.filter(item => item.done).length;
  const pages = entries.filter(entry => "tab" in entry.target && entry.target.tab !== "users");
  return <div className="grid min-w-0 gap-5 py-4">
    {allowedTabs.includes("users") ? <Link to={tabHref("users")}
      className="flex min-h-11 min-w-0 items-center gap-3 rounded-xl border border-line bg-surface p-4 hover:bg-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">
      <Users aria-hidden="true" size={24} className="shrink-0 text-accent-ink" />
      <span className="grid min-w-0 flex-1 gap-0.5"><span className="font-semibold text-ink">Staff & roles</span>
        <span className="text-sm text-muted">Create staff accounts for this space, assign their roles and the machine types they manage.</span></span>
      <span aria-hidden="true" className="text-muted">→</span>
    </Link> : null}
    <div role="search" className="grid min-w-0 gap-2">
      <label className="text-sm font-semibold text-ink" htmlFor="settings-hub-search">Search settings</label>
      <input id="settings-hub-search" type="search" className="desk-input w-full" value={query} placeholder="Try “WhatsApp”, “loan days” or “logo”"
        onChange={event => setQuery(event.target.value)} />
    </div>
    {query.trim() ? <section aria-label="Search results" className="grid min-w-0 gap-1">
      <p aria-live="polite" className="text-sm text-muted">{results.length ? `${results.length} matching setting${results.length === 1 ? "" : "s"}` : "No settings match. Try another word."}</p>
      <ul className="grid min-w-0 gap-1">{results.map((entry: HubEntry) => <li key={entry.id}>
        <Destination target={entry.target} tabHref={tabHref}><span className="grid min-w-0 gap-0.5">
          <span className="font-semibold text-ink">{entry.title}</span><span className="text-muted">{entry.description}</span></span></Destination>
      </li>)}</ul>
    </section> : <>
      <section aria-label="Setup checklist" className="grid min-w-0 gap-2">
        <div className="flex flex-wrap items-baseline justify-between gap-2"><h3 className="title-section">Setup checklist</h3>
          <span className="text-sm text-muted tabular-nums">{done} of {checklist.length} done</span></div>
        <ProgressBar value={checklist.length ? done / checklist.length : 0} label="Setup progress" />
        <ul className="grid min-w-0 gap-1 sm:grid-cols-2">{checklist.map(item => <li key={item.id}>
          <Destination target={item.target} tabHref={tabHref}>
            {item.done ? <CheckCircle2 aria-hidden="true" size={20} className="shrink-0 text-success-ink" /> : <Circle aria-hidden="true" size={20} className="shrink-0 text-muted" />}
            <span className={item.done ? "text-muted" : "font-semibold text-ink"}>{item.label}<span className="sr-only">{item.done ? " (done)" : " (to do)"}</span></span>
          </Destination></li>)}</ul>
      </section>
      {pages.length ? <section aria-label="More settings pages" className="grid min-w-0 gap-1">
        <h3 className="title-section">More settings</h3>
        <ul className="grid min-w-0 gap-1 sm:grid-cols-2">{pages.map(entry => <li key={entry.id}>
          <Destination target={entry.target} tabHref={tabHref}><span className="grid min-w-0 gap-0.5">
            <span className="font-semibold text-ink">{entry.title}</span><span className="text-muted">{entry.description}</span></span></Destination>
        </li>)}</ul>
      </section> : null}
    </>}
  </div>;
}

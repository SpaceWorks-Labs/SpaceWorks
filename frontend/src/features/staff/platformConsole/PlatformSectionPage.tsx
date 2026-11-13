import type { ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { SettingsLayout } from "../../../components/layouts";
import { Tabs } from "../../../components/ui";

/**
 * One platform page with routed sections (`?section=<key>`): a section is either rows inside
 * this page's settings layout, or a whole existing page (Staff & roles, Backup & restore)
 * shown under the same section tabs so nothing is rebuilt.
 */
export type PlatformSection = { key: string; label: string; description?: string; rows?: ReactNode; page?: ReactNode };

export function sectionHref(search: URLSearchParams, key: string) {
  const next = new URLSearchParams(search);
  next.set("section", key);
  return `?${next}`;
}

export function PlatformSectionPage({ title, subtitle, sections }: { title: string; subtitle: string; sections: PlatformSection[] }) {
  const [search] = useSearchParams();
  const active = sections.find(section => section.key === search.get("section")) ?? sections[0];
  const tabs = sections.map(section => ({ key: section.key, label: section.label, href: sectionHref(search, section.key) }));
  if (active.page) return <>
    <div className="mb-6"><Tabs label={title} tabs={tabs} activeKey={active.key} /></div>
    {active.page}
  </>;
  return <SettingsLayout header={{ title, subtitle }} state={{ status: "ready" }} tabs={tabs} activeTab={active.key}
    sections={[{ id: active.key, title: active.label, description: active.description, rows: active.rows }]} />;
}

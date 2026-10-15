import { isValidElement, type ReactNode } from "react";
import { DangerZone, ErrorBlock, PageHeader, SettingsActions, SettingsRow, SettingsSection, Tabs } from "../ui";
import type { DangerZoneProps, PageHeaderProps, SettingsActionsProps, SettingsRowProps, Tab } from "../ui";
import { LayoutFrame, QueryContent } from "./LayoutFrame";
import { SettingsNav } from "./SettingsNav";
import type { LayoutProps } from "./types";

export type SettingsSave = SettingsActionsProps & { dirty: boolean; error?: string };
export type SettingsLayoutSection = { id: string; title?: string; description?: string;
  rows: SettingsRowProps[] | ReactNode; save?: SettingsSave };
export type SettingsLayoutProps = LayoutProps & {
  header: PageHeaderProps & { subtitle: string };
  tabs?: Tab[];
  activeTab?: string;
  subnav?: "auto" | false;
  sections: SettingsLayoutSection[];
  actions?: SettingsSave;
  danger?: DangerZoneProps[];
};

function Rows({ rows }: { rows: SettingsLayoutSection["rows"] }) {
  if (Array.isArray(rows) && rows.every(row => row && !isValidElement(row) && typeof row === "object" && "label" in row)) {
    return <>{(rows as SettingsRowProps[]).map((row, index) => <div key={`${row.label}-${index}`} className="sw-settings-row"><SettingsRow {...row} /></div>)}</>;
  }
  return <>{rows as ReactNode}</>;
}
function SaveActions({ save }: { save: SettingsSave }) {
  return save.dirty || save.pending || save.error ? <div className="sticky bottom-0 z-10 bg-panel">
    {save.error ? <ErrorBlock error={new Error(save.error)} /> : null}
    <SettingsActions {...save} />
  </div> : null;
}
export function SettingsLayout({ header, tabs, activeTab, subnav = "auto", sections, actions, danger = [],
  standalone, width, ...query }: SettingsLayoutProps) {
  const showNav = subnav === "auto" && sections.length >= 5;
  return <LayoutFrame standalone={standalone} width={width}>
    <PageHeader {...header} />
    {tabs?.length ? <div className="mb-6"><Tabs tabs={tabs} activeKey={activeTab ?? tabs[0].key} /></div> : null}
    <QueryContent {...query}>
      <div className={showNav ? "sw-settings-columns" : "min-w-0"}>
        {showNav ? <SettingsNav sections={sections} /> : null}
        <div className="grid min-w-0 content-start gap-8">
          {sections.map(section => <div key={section.id} id={section.id} tabIndex={-1}
            className="min-w-0 scroll-mt-6 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">
            <SettingsSection title={section.title ?? section.id} description={section.description}><Rows rows={section.rows} /></SettingsSection>
            {section.save ? <SaveActions save={section.save} /> : null}
          </div>)}
          {actions ? <SaveActions save={actions} /> : null}
          {danger.map(zone => <DangerZone key={zone.title} {...zone} />)}
        </div>
      </div>
    </QueryContent>
  </LayoutFrame>;
}

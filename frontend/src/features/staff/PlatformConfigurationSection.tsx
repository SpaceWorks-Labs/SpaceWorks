import type { ReactNode } from "react";
import { SettingsLayout, type SettingsSave } from "../../components/layouts";
import { QueryContent } from "../../components/layouts/LayoutFrame";
import { DangerZone, SettingsActions } from "../../components/ui";
import type { DangerZoneProps, QueryState } from "../../components/ui";
type Props = { title: string; subtitle: string; state: QueryState; children: ReactNode;
  save: SettingsSave; embedded?: boolean; danger?: DangerZoneProps[] };

export function PlatformConfigurationSection({ title, subtitle, state, children, save, embedded, danger = [] }: Props) {
  if (!embedded) return <SettingsLayout header={{ title, subtitle }} state={state}
    sections={[{ id: "configuration", title, rows: children, save }]} danger={danger} />;
  return <QueryContent state={state}><div className="grid gap-4"><p className="text-sm text-muted">{subtitle}</p>{children}
    {save.error ? <p className="text-sm text-danger" role="alert">{save.error}</p> : null}
    {save.dirty || save.pending || save.error ? <SettingsActions {...save} /> : null}
    {danger.map(zone => <DangerZone key={zone.title} {...zone} />)}
  </div></QueryContent>;
}

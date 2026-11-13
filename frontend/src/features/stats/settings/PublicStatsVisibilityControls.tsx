import { t } from "@lingui/core/macro";
import { useId } from "react";
import { SettingsRow } from "../../../components/ui";
import type { PublicStatsSettings, PublicStatsSettingsResponse } from "./api";
import { statsDecision, statsEditable, statsVisible } from "./visibility";
import { SettingLock } from "../../staff/SettingLock";

export function PublicStatsVisibilityControls({ makerspaceId, response, value, area, onChange }: {
  makerspaceId: number; response: PublicStatsSettingsResponse; value: PublicStatsSettings; area?: string;
  onChange: (key: string, visible: boolean) => void;
}) {
  const id = useId();
  const widgets = (response.choices.widgets ?? []).filter(widget => (!area || widget.owner_module === area)
    && statsDecision(response, "visibility", widget.key).available !== false);
  if (!widgets.length) return null;
  return <SettingsRow label={t`What appears in public stats`}
    helper={t`Choose the figures and lists visitors can see. These choices also apply to the TV board. Turning one off keeps its data.`}>
    <div className="grid gap-5">
      {response.choices.sections.map(section => {
        const entries = widgets.filter(widget => widget.section === section.key);
        if (!entries.length) return null;
        return <fieldset key={section.key} className="grid gap-3">
          <legend className="mb-2 text-sm font-semibold">{section.label}</legend>
          {entries.map(widget => {
            const decision = statsDecision(response, "visibility", widget.key);
            const editable = statsEditable(decision);
            const inputId = `${id}-${widget.key}`;
            return <div key={widget.key} className="grid gap-1">
              <label htmlFor={inputId} className="flex min-h-11 items-center gap-3 text-sm">
                <input id={inputId} type="checkbox" checked={statsVisible(value, widget.key)} disabled={!editable}
                aria-describedby={decision.locked || !editable ? `${inputId}-reason` : undefined}
                  onChange={event => onChange(widget.key, event.target.checked)} />{widget.label}
              </label>
              {decision.locked || !editable ? <p id={`${inputId}-reason`} className="text-sm text-muted">
                {decision.locked ? editable ? t`Locked for delegated managers. You can override this lock.` : t`This setting is locked.` : t`Only the responsible manager can change this setting.`}
              </p> : null}
              <SettingLock makerspaceId={makerspaceId} settingKey={`public_stats.visibility.${widget.key}`}
                label={widget.label} locked={decision.locked} canLock={decision.can_lock === true} />
            </div>;
          })}
        </fieldset>;
      })}
    </div>
  </SettingsRow>;
}

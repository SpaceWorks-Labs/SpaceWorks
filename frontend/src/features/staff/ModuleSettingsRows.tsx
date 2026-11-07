import { t } from "@lingui/core/macro";
import { SettingsRow, StatusPill } from "../../components/ui";
import { toast } from "../../components/ui/toastStore";

export type ModuleRow = {
  key: string; label: string; description: string; installed: boolean; core: boolean;
  available: boolean; requires: string[]; pulls_in: string[]; required_by: string[]; workflows: string[];
  /** #128 C-10: on the managed platform a limit-gated install is the superadmin's. */
  install_requires_superadmin?: boolean; limits?: string[];
};
export type ModuleGroup = {
  key: string; label: string; description: string; always_on: boolean;
  installed_count: number; module_count: number; modules: ModuleRow[];
};
export type ModulesResponse = {
  groups: ModuleGroup[];
  /** Superadmin only: what this deployment ships. */
  deployment: { apps: { app_label: string; shipped: boolean; note: string }[]; env_line: string; requires_restart: boolean } | null;
};

export function ModuleSettingsRow({ module, pending, onChange }: {
  module: ModuleRow; pending: boolean; onChange: (action: "install" | "uninstall") => void;
}) {
  const blocked = module.installed && module.required_by.length > 0;
  const gated = !module.installed && module.install_requires_superadmin === true;
  const reason = blocked ? `Turn off ${module.required_by.join(", ")} first.`
    : !module.available ? "Not shipped by this deployment."
    : gated ? "This module has a usage limit on this platform. Ask the platform administrator to turn it on." : undefined;
  return <SettingsRow label={module.label} helper={module.description}>
    <div className="@container grid gap-2">
      {module.core ? <StatusPill tone="neutral" label={t`Always on`} />
        : <label className="flex min-h-11 cursor-pointer items-center gap-3 rounded-control focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-focus">
          <input type="checkbox" role="switch" aria-label={module.label} aria-describedby={reason ? `module-${module.key}-reason` : undefined}
            className="h-5 w-5 accent-accent" checked={module.installed} disabled={pending || blocked || gated || (!module.installed && !module.available)}
            onChange={() => onChange(module.installed ? "uninstall" : "install")} />
          <span className="text-sm text-ink">{pending ? t`Updating…` : module.installed ? t`On` : t`Off`}</span>
        </label>}
      {module.workflows.length ? <p className="text-sm text-muted">{t`Turns on: ${module.workflows.join(", ")}`}</p> : null}
      {!module.installed && module.pulls_in.length ? <p className="text-sm text-muted">{t`Also installs: ${module.pulls_in.join(", ")}`}</p> : null}
      {reason ? <p id={`module-${module.key}-reason`} className="text-sm text-muted">{reason}</p> : null}
      {!module.installed && module.required_by.length ? <p className="text-sm text-muted">{t`Required by ${module.required_by.join(", ")}`}</p> : null}
    </div>
  </SettingsRow>;
}

export function DeploymentModules({ deployment }: { deployment: NonNullable<ModulesResponse["deployment"]> }) {
  return <div className="grid gap-3">
    <p className="text-sm text-muted">{t`Deployment apps are set at startup. Copy this line into your environment and restart to change what is shipped for every space.`}</p>
    {deployment.apps.map(app => <SettingsRow key={app.app_label} label={app.app_label} helper={app.note}>
      <StatusPill tone={app.shipped ? "success" : "neutral"} label={app.shipped ? t`Shipped` : t`Removed`} />
    </SettingsRow>)}
    <pre className="overflow-auto rounded-control border border-line bg-surface p-4 text-sm text-ink"><code>{deployment.env_line}</code></pre>
    <button type="button" className="desk-button w-fit" onClick={async () => { try { await navigator.clipboard.writeText(deployment.env_line); toast(t`Environment line copied.`); } catch { toast(t`Couldn't copy. Select and copy the environment line.`, { tone: "error" }); } }}>{t`Copy environment line`}</button>
  </div>;
}

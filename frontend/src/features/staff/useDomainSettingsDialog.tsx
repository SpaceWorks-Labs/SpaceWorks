import { useState, type ReactNode } from "react";

import { Modal } from "../../components/ui";
import type { Action } from "../../components/ui/types";
import { DomainSettingsSection } from "./DomainSettingsSection";
import { DOMAIN_TITLES, type SettingsDomain } from "./domainSettingsApi";

/**
 * An overflow-menu entry plus its dialog, so a domain console mounts its settings with one
 * call: spread `action` into the header's `overflow` and render `dialog` once. `allowed` is
 * the caller's own gate for the domain action; the server re-checks it on every request.
 */
export function useDomainSettingsDialog(
  makerspaceId: number,
  domain: SettingsDomain,
  allowed = true,
): { actions: Action[]; dialog: ReactNode } {
  const [open, setOpen] = useState(false);
  const title = DOMAIN_TITLES[domain];
  return {
    actions: allowed ? [{ label: title, icon: "Settings", onClick: () => setOpen(true) }] : [],
    dialog: <Modal open={open && allowed} title={title} size="xl" onClose={() => setOpen(false)}>
      {open && allowed ? <DomainSettingsSection makerspaceId={makerspaceId} domain={domain} /> : null}
    </Modal>,
  };
}

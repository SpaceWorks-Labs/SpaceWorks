import { useState, type ReactNode } from "react";

import { Modal } from "../../components/ui";
import type { Action } from "../../components/ui/types";
import { DomainSettingsSection } from "./DomainSettingsSection";
import { AreaPricingSection } from "./areaPayments/AreaPricingSection";
import { DOMAIN_TITLES, type SettingsDomain } from "./domainSettingsApi";
import { PublicStatsSettingsPanel } from "../stats/settings/PublicStatsSettingsPanel";

/**
 * An overflow-menu entry plus its dialog, so a domain console mounts its settings with one
 * call: spread `action` into the header's `overflow` and render `dialog` once. `allowed` is
 * the caller's own gate for the domain action; the server re-checks it on every request.
 * `extra` adds the domain's own editors below the shared switches (Inventory: loan policy).
 * Decision 242(d): every area also shows its rate card and its read-only "Charging on/off" line.
 */
export function useDomainSettingsDialog(
  makerspaceId: number,
  domain: SettingsDomain,
  allowed = true,
  extra?: ReactNode,
  publicStats = false,
): { actions: Action[]; dialog: ReactNode } {
  // Decision 255: Settings › Areas links here with `?settings=open`, so the dialog opens on arrival.
  const [open, setOpen] = useState(() => new URLSearchParams(window.location.search).get("settings") === "open");
  const title = DOMAIN_TITLES[domain];
  const close = () => {
    setOpen(false);
    const url = new URL(window.location.href);
    if (url.searchParams.get("settings") !== "open") return;
    url.searchParams.delete("settings");
    window.history.replaceState(window.history.state, "", url.pathname + url.search + url.hash);
  };
  return {
    actions: allowed ? [{ label: title, icon: "Settings", onClick: () => setOpen(true) }] : [],
    dialog: <Modal open={open && allowed} title={title} size="xl" onClose={close}>
      {open && allowed ? <><DomainSettingsSection makerspaceId={makerspaceId} domain={domain} />
        <AreaPricingSection makerspaceId={makerspaceId} domain={domain} />{extra}
        {publicStats ? <PublicStatsSettingsPanel makerspaceId={makerspaceId} slug="" area={domain} /> : null}</> : null}
    </Modal>,
  };
}

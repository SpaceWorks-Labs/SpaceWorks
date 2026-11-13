import { t } from "@lingui/core/macro";
import type { ModuleKey } from "../../../../lib/retiredModules";
import { eventsAndBookings } from "./eventsBookings";
import { inventorySpine } from "./inventory";
import { inventoryStock } from "./inventoryStock";
import { machinesAndDevices } from "./machines";
import { membershipAndMobile } from "./membership";
import { messaging } from "./messaging";
import { moneyAndReports } from "./moneyReports";
import { limitLabel } from "../../../staff/platformSpaces/limitCopy";
import { MODULE_LIMIT_KEYS } from "./limitData";
import { REGISTRY } from "./registryData";
import { dashboardTitle, reportTitle, viewTitle } from "./registryTitles";
import type { Catalogue, CataloguePart } from "./types";

export type { Catalogue, ModuleEntry, Screenshot } from "./types";

/**
 * Every module's page content. Hand-written parts (what it does, roles, integrations, 0.12.0 news) are merged with
 * what the registries say: reports and analytics from registryData, limits from limitData. A function so a
 * language switch re-translates; the cast is checked by catalogue.test.ts (every module has an entry).
 */
export function featureCatalogue(): Catalogue {
  const written: CataloguePart = {
    ...inventorySpine(), ...inventoryStock(), ...machinesAndDevices(), ...eventsAndBookings(), ...membershipAndMobile(),
    ...messaging(), ...moneyAndReports(),
  };
  return Object.fromEntries(Object.entries(written).map(([key, content]) => {
    const row = REGISTRY[key] ?? { reports: [], views: [], dashboards: [] };
    return [key, { ...content,
      reports: row.reports.map(report => ({ key: report, title: reportTitle(report) })),
      analytics: [...row.views.map(view => t`${viewTitle(view)} (Metabase view)`), ...row.dashboards.map(board => t`${dashboardTitle(board)} (Grafana)`)],
      limits: (MODULE_LIMIT_KEYS[key] ?? []).map(limit => limitLabel(limit)) }];
  })) as Catalogue;
}

export type NewIn = { module: ModuleKey; title: string; line: string };

/** The "New in 0.12.0" strip: each links to the module page that lists it. */
export function newInRelease(): NewIn[] {
  return [
    { module: "membership", title: t`Card Studio and certificates`, line: t`Design member cards, staff IDs and certificates, with a background eraser for photos.` },
    { module: "reports", title: t`Reports for every module`, line: t`One hub grouped by module, scheduled and exported, with platform roll-ups.` },
    { module: "devices", title: t`Device adapters`, line: t`Video, audio and media players, a shelf pointer and kiosk checkout.` },
    { module: "machines", title: t`Machine access grants`, line: t`A space manager gives access per machine and person.` },
    { module: "presence", title: t`Displays and Anthias`, line: t`Paired TV screens and Anthias signage players.` },
    { module: "member_accounts", title: t`Global profiles and usernames`, line: t`One profile across spaces, with a username you choose.` },
    { module: "staff_admin", title: t`Colour settings and module switches`, line: t`Brand colours with a live preview, and switches grouped by module.` },
    { module: "request_workflow", title: t`Limits per module`, line: t`Off by default; a platform default per module, overridable per space.` },
  ];
}

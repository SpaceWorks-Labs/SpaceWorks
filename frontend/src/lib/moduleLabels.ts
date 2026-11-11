import { t } from "@lingui/core/macro";
import type { ModulesEnum } from "../generated/api";

// Module and workflow keys as people read them, in the active language. The words follow the
// backend registry (apps/makerspaces/module_registry_catalog.py and siblings), which is the
// single source of truth for the keys; typing the map by the generated ModulesEnum makes a
// newly registered module a type error here until it has a name. Functions, not constants,
// so a language switch relabels.
const MODULE_NAMES = (): Record<ModulesEnum, string> => ({
  public_inventory: t`Public inventory`, request_workflow: t`Request workflow`, staff_admin: t`Staff admin`,
  guest_handover: t`Guest handover`, scanner: t`Scanner`, printing: t`Printing`, telegram: t`Telegram`,
  evidence_uploads: t`Evidence uploads`, qr_management: t`QR management`, bulk_import: t`Bulk import`,
  containers: t`Containers`, stock_transfers: t`Stock transfers`, stocktake: t`Stocktake`, reports: t`Reports`,
  qr_print_batches: t`QR print batches`, asset_units: t`Asset units`, machines: t`Machines`,
  machine_service: t`Machine service`, events: t`Events`, event_reimbursements: t`Event reimbursements`,
  bookings: t`Bookings`, membership: t`Membership`, notifications: t`Notifications`, email: t`Email`, sms: t`SMS`,
  whatsapp: t`WhatsApp`, slack: t`Slack`, mattermost: t`Mattermost`, discord: t`Discord`, webhook: t`Signed webhooks`,
  payments: t`Payments`, member_accounts: t`Member accounts`, mobile: t`Mobile apps`, devices: t`Connected devices`,
  presence: t`Presence`, shop: t`Shop`, analytics: t`Analytics (Metabase, Grafana)`,
});

// The frontend workflows each module turns on (`frontend_workflows` in the same registry).
const WORKFLOW_NAMES = (): Record<string, string> => ({
  analytics: t`Analytics`, asset_qr_generation: t`Asset QR codes`, bulk_import: t`Bulk import`, catalog: t`Catalogue`,
  container_lookup: t`Container lookup`, container_move: t`Container moves`, evidence_uploads: t`Evidence uploads`,
  guest_issue: t`Handover issue`, guest_return: t`Handover return`, machine_service_requests: t`Machine service requests`,
  presence_checkin: t`Presence check-in`, presence_display: t`Presence display`, printing_requests: t`Print requests`,
  qr_generate: t`QR generation`, qr_print: t`QR printing`, qr_print_batch: t`QR print batches`, qr_revoke: t`QR revocation`,
  qr_scan: t`QR scanning`, report_export: t`Report exports`, request_status: t`Request status`,
  request_submit: t`Request submission`, staff_inventory: t`Staff inventory`, staff_requests: t`Staff requests`,
  stock_transfer: t`Stock transfers`, stocktake: t`Stocktake`, telegram_alerts: t`Telegram alerts`,
});

const words = (key: string) => {
  const text = key.replace(/_/g, " ").trim();
  return text.charAt(0).toUpperCase() + text.slice(1);
};

/** A module key as a translated name; a retired or unknown key falls back to its words. */
export function moduleLabel(key: string): string {
  return (MODULE_NAMES() as Record<string, string>)[key] ?? words(key);
}

/** Every module key this build knows (the generated ModulesEnum), for pickers. */
export function moduleKeys(): ModulesEnum[] {
  return Object.keys(MODULE_NAMES()) as ModulesEnum[];
}

/** Several module keys as one readable, comma-separated list. */
export function moduleList(keys: readonly string[]): string {
  return keys.map(moduleLabel).join(", ");
}

/** A frontend workflow key as a translated name; an unknown key falls back to its words. */
export function workflowLabel(key: string): string {
  return WORKFLOW_NAMES()[key] ?? words(key);
}

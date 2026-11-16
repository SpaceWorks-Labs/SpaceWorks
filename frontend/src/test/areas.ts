/** Frontend directory ownership; names mirror backend/tests/areas.py. Node 22+ CLI. */
import { spawnSync } from "node:child_process";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const shell = ["src/App", "src/cloudEdge", "src/edgeSecurity", "src/sw", "src/lib", "src/components", "src/test"];
const staff = ["src/features/staff"];
const loans = ["src/features/inventory", "src/features/loanDelight", "src/features/kiosk"];
const machines = ["src/features/machine-", "src/features/supervised-sessions", "src/features/printing"];
const members = ["src/features/members", "src/features/community", "src/features/profile", "src/features/cards",
  "src/features/cardEraser", "src/features/walletCredentials", "src/features/guestPasses"];
const messages = ["src/features/notifications", "src/features/messaging"];
const money = ["src/features/payments", "src/features/finance", "src/features/donations"];

export const areas: Record<string, readonly string[]> = {
  analytics: [...staff, "src/features/stats"],
  api_contract: shell,
  asset_units: loans,
  audit: staff,
  auth: ["src/features/auth", "src/features/accountSavedDetails"],
  backup: [...staff, "src/features/deployment"],
  bookings: ["src/features/bookings", "src/features/bookingDelight", "src/features/repairs", ...staff],
  bulk_import: [...loans, ...staff],
  containers: [...loans, ...staff],
  data_export: [...staff, "src/features/accountActivity"],
  devices: [...staff, "src/features/kiosk", ...machines],
  discord: [...messages, ...staff],
  email: [...messages, ...staff],
  event_reimbursements: ["src/features/events", ...money, ...staff],
  events: ["src/features/events", ...staff],
  evidence_uploads: [...loans, ...machines, ...staff],
  forms: ["src/features/forms", ...staff],
  frontend_shell: [...shell, "src/features/public", "src/features/landing", "src/features/discover",
    "src/features/legal", "src/features/docs", "src/features/help", "src/features/hub", "src/features/AboutPage",
    "src/features/LandingPage", "src/features/NotFoundPage"],
  guest_handover: [...loans, ...machines, ...staff],
  inventory: [...loans, "src/features/repairs", "src/features/incidents", ...staff],
  lending: [...loans, ...staff],
  machine_service: [...machines, ...staff],
  machines: [...machines, "src/features/repairs", "src/features/incidents", ...staff],
  mattermost: [...messages, ...staff],
  member_accounts: ["src/features/auth", ...members, "src/features/accountSavedDetails"],
  membership: [...members, "src/features/accountActivity", ...staff],
  mobile: ["src/features/auth", "src/features/walletCredentials", ...messages, ...money],
  notifications: [...messages, ...staff],
  organizations: ["src/features/organizations", "src/features/organizationLeave", ...staff],
  payments: [...money, ...staff],
  payments_ledger: [...money, "src/features/accountActivity", ...staff],
  platform: ["src/features/deployment", "src/features/hosting", "src/features/platform", ...staff],
  presence: ["src/features/presence", "src/features/spaceDisplay", ...staff],
  public_inventory: [...loans, "src/features/public"],
  qr_management: [...loans, ...members, ...staff],
  qr_print_batches: [...loans, ...staff],
  reports: [...staff, "src/features/stats", ...money],
  request_workflow: [...loans, ...staff],
  scanner: [...loans, ...members, ...staff],
  shop: ["src/features/shop", ...staff],
  slack: [...messages, ...staff],
  sms: [...messages, "src/features/auth", ...staff],
  staff_admin: staff,
  stock_transfers: [...loans, ...staff],
  stocktake: [...loans, ...staff],
  telegram: [...messages, ...staff],
  tenancy: shell,
  tenant_migration: [...staff, "src/features/deployment"],
  webhook: [...messages, ...staff],
  whatsapp: [...messages, ...staff],
};

export function pathsForAreas(names: readonly string[]): string[] {
  const unknown = names.filter(name => !Object.prototype.hasOwnProperty.call(areas, name));
  if (unknown.length) throw new Error(`Unknown areas: ${unknown.join(", ")}; use --list`);
  if (!names.length) throw new Error("Supply at least one area; use --list");
  // Shared gate/permission, shell and component tests accompany every feature run.
  return [...new Set([...names.flatMap(name => areas[name]), ...shell])].sort();
}

export function main(args = process.argv.slice(2)): number {
  if (args.length === 1 && args[0] === "--list") {
    console.log(Object.keys(areas).sort().join("\n"));
    return 0;
  }
  const optionIndex = args.findIndex(arg => arg.startsWith("-"));
  const names = (optionIndex < 0 ? args : args.slice(0, optionIndex)).flatMap(arg => arg.split(/[,\s]+/)).filter(Boolean);
  const options = optionIndex < 0 ? [] : args.slice(optionIndex);
  try {
    const paths = pathsForAreas(names);
    const result = spawnSync(process.execPath, [fileURLToPath(new URL("../../node_modules/vitest/vitest.mjs", import.meta.url)),
      "run", ...paths, ...options], { cwd: fileURLToPath(new URL("../..", import.meta.url)), stdio: "inherit" });
    if (result.error) throw result.error;
    return result.status ?? 1;
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    return 2;
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) process.exitCode = main();

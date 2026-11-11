// What the in-app /docs shows. Two sources, both from the repository's docs/ folder:
//
// 1. Whole folders written for the docs site. Every Markdown file in them is published; its front
//    matter (title, group, order, summary, updated) places it, and the folder names the group when
//    front matter does not.
// 2. A curated list of the older user-facing guides at the top of docs/. Developer-internal notes
//    (INVARIANTS, SOURCE-MAP*, DEV-WORKFLOW, PROJECT-*, security/ working notes, landing-page
//    research, batch notes) are deliberately absent: they stay on GitHub, and a link to one from a
//    published page opens it there.

/** The sidebar order. A page whose group is not listed sorts after these, alphabetically. */
export const DOC_GROUPS = [
  "Getting started", "Tutorials", "User guides", "How-to guides", "Areas & modules", "Architecture",
  "Hosting", "API", "Reference", "Project", "Changelog",
] as const;

export const DOC_FOLDERS: Record<string, string> = {
  guide: "Getting started",
  tutorials: "Tutorials",
  "user-guides": "User guides",
  "how-to": "How-to guides",
  modules: "Areas & modules",
  architecture: "Architecture",
  hosting: "Hosting",
  api: "API",
  reference: "Reference",
  project: "Project",
  changelog: "Changelog",
};

type Curated = { source: string; group: (typeof DOC_GROUPS)[number]; title?: string };

const group = (name: Curated["group"], sources: string[]): Curated[] => sources.map(source => ({ source, group: name }));

/** Order inside a group follows this list; folder pages (with an `order`) come first. */
export const CURATED_DOCS: Curated[] = [
  ...group("Getting started", ["setup-for-makerspaces.md", "FEATURES.md", "choose-your-hosting.md"]),
  ...group("User guides", [
    "USER-MANUALS.md", "operator-manual.md", "sign-in-and-borrowing.md", "loan-policy.md", "equipment-kits.md",
    "equipment-contexts.md", "equipment-reports.md", "machine-training-maintenance.md", "membership-admission.md",
    "member-account-renewals.md", "RBAC-MEMBERS-FINANCE.md", "payment-billing.md", "payment-documents.md",
    "notification-inbox.md", "notification-routing.md", "SPACE-PACKS.md", "KIOSK-OFFLINE.md", "KIOSK-RECOVERY.md",
    "events/README.md", "events/organizer.md", "events/participant.md", "events/mentor.md", "events/volunteer.md",
    "events/judge.md", "events/media.md", "events/staged-forms.md", "events/reimbursement.md",
  ]),
  ...group("Areas & modules", [
    "MODULES.md", "choosing-modules.md", "MODULES-INVENTORY.md", "MODULES-WORKSHOPS.md", "MODULES-PLATFORM.md",
    "MODULES-LIFECYCLE.md", "MODULES-OFF.md", "wallet-passes.md", "messaging-channels.md",
  ]),
  ...group("Hosting", [
    "install-and-update.md", "self-hosting.md", "README-HOSTING.md", "deploy-production.md", "own-domain-and-frontend.md",
    "single-tenant-frontend.md", "backup-and-restore.md", "update-recovery.md", "upgrade-to-0.12.0.md",
    "account-portability.md", "scoped-pii-encryption.md", "helm.md", "supabase-deployment.md",
    "monitoring-and-analytics.md", "grafana-setup.md", "metabase-setup.md", "analytics-views.md", "platform-monitoring.md",
    "web-telemetry-providers.md", "events/operations.md", "events/reimbursement-operations.md",
    "deploy/cloud-overview.md", "deploy/mix-and-match.md", "deploy/cloud-docker.md", "deploy/cloud-free.md",
    "deploy/cloud-hetzner-coolify.md", "deploy/cloud-oracle-free.md", "deploy/cloud-aws.md", "deploy/cloud-azure.md",
    "deploy/cloud-cloud-run.md", "deploy/cloud-digitalocean.md", "deploy/cloud-fly.md", "deploy/cloud-koyeb.md",
    "deploy/cloud-railway.md", "deploy/cloud-render.md", "deploy/cloud-kubernetes.md", "deploy/cloud-static.md",
    "deploy/cloud-environment.md", "deploy/cloud-recovery.md", "deploy/cloud-contracts.md", "i18n.md",
  ]),
  ...group("API", [
    "api-guide.md", "api-client-protocol.md", "webhooks-v2.md", "mobile-integration.md", "device-protocol.md",
    "device-printer-protocol.md", "device-label-commands.md", "machine-integrations/INTEGRATION.md",
  ]),
  ...group("Reference", [
    "environment-reference.md", "environment-reference-delivery.md", "environment-operations.md",
    "logging-and-audit.md", "audit-action-reference.md", "reminder-schedules.md", "privacy-account-deletion.md",
    "privacy-sheet-import.md",
  ]),
  ...group("Project", ["future-work.md", "security-summary-0.12.0.md"]),
  ...group("Changelog", ["release-0.12.0.md", "release-0.11.0.md", "upgrade-to-0.11.0.md", "security-summary-0.11.0.md"]),
];

/** `README-HOSTING.md` opens with a banner, not a `# Title`. */
export const TITLE_OVERRIDES: Record<string, string> = { "README-HOSTING.md": "Hosting and roles" };

/** Route id for a source path: `hosting/docker.md` → `hosting/docker`, `events/README.md` → `events`. */
export function docId(source: string) {
  return source.replace(/\.md$/i, "").replace(/(^|\/)(README|index)$/i, "").toLowerCase() || "overview";
}

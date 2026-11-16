import type { RouteCase } from "./source.census-D12";
import type { Phase } from "./fetch.census-D12";
import { contextlessNotice } from "./contextless.census-D12";

type Proof = { kind: string; mounts: string[]; destination?: string; admissionOnly?: boolean };
const staticScreens = new Set(["NotFoundPage", "FeaturesPage", "FeatureModulePage", "HelpPage", "DocsPage", "GithubAppCallbackPage"]);

/** Explicit presentation/mount contracts. A new exemption cannot silently inherit a generic main/loader check. */
export function exemptionProofFor(row: RouteCase, phase: Phase): Proof {
  if (contextlessNotice(row, phase)) return { kind: "contextless", mounts: [row.screen] };
  if (staticScreens.has(row.screen)) return { kind: row.screen, mounts: [row.screen], admissionOnly: true };
  if (["AboutLandingGate", "LandingGate", "FamilyHome"].includes(row.screen)) return { kind: row.screen, mounts: [row.screen] };
  if (row.screen === "SpaceDisplayPage" && phase === "permission") return { kind: row.screen, mounts: [row.screen] };
  if (row.screen === "SingleTenantHome") return { kind: "tenant-home", mounts: ["FamilyHome", "MakerspacePage"], destination: "/" };
  if (row.screen === "PrintRequestAlias") return { kind: "print-alias", mounts: ["JobRequestPage"],
    destination: row.mode === "single" ? "/machine-jobs/new" : "/m/lab/machine-jobs/new" };
  if (row.screen === "SuperadminPage") return { kind: "superadmin-alias", mounts: ["StaffApp", "MakerspacePicker"],
    destination: "/superadmin" };
  if (row.screen === "Navigate" && row.file === "features/events/programme/EventProgrammePage.tsx") return {
    kind: "programme-index", mounts: ["HackathonApplicationPage"], destination: `${row.path}/application`,
  };
  if (row.screen === "p" && row.file === "features/events/programme/EventProgrammePage.tsx") return {
    kind: "programme-missing", mounts: ["EventProgrammePage", "MemberContent", "p"],
  };
  if (row.screen === "ReauthenticationReturn" && row.pattern === "/reauth/callback") return { kind: "reauth-callback", mounts: [row.screen] };
  if (row.screen === "ReauthenticationReturn" && row.pattern === "/reauth/confirm" && phase === "module") return { kind: "reauth-confirm", mounts: [row.screen] };
  throw new Error(`No mounted presentation proof for exemption: ${row.id} / ${phase}`);
}


import { t } from "@lingui/core/macro";
import { ThemeToggle } from "../../components/ThemeToggle";
import { LanguageSwitcher } from "../../components/shell/LanguageSwitcher";
import { MakerspaceMapLink } from "../../components/MakerspaceMapLink";
import type { TenantBootstrap } from "../../lib/api";
import { publicFamilies } from "../../lib/publicHome";

export const LICENSE_URL = "https://github.com/SpaceWorks-Labs/SpaceWorks/blob/main/LICENSE";

/** Shared public navigation derives only from the bootstrap already loaded by its caller. */
export function publicPageChrome(slug: string, name: string, path: (part?: string) => string, bootstrap?: TenantBootstrap | null) {
  const modules = new Set(bootstrap?.modules ?? []);
  // #183B: the inventory entry follows its live publication and lending gates.
  const nav: { label: string; href: string }[] = [{ label: t`Home`, href: path() }];
  if (!bootstrap || publicFamilies(bootstrap).includes("inventory")) nav.push({ label: t`Inventory`, href: path("inventory") });
  if (modules.has("events")) nav.push({ label: t`Events`, href: path("events") });
  if (modules.has("machines")) nav.push({ label: t`Machines`, href: path("machines") });
  if (modules.has("bookings")) nav.push({ label: t`Book a space`, href: path("bookings") });
  // One "Request a job" flow for every machine type (#140); the 3D-print link survives only where it is off.
  if (modules.has("machine_service") && bootstrap?.features?.includes("machines.job_requests")) nav.push({ label: t`Request a job`, href: path("machine-jobs/new") });
  else if (modules.has("printing")) nav.push({ label: t`Request a 3D print`, href: path("print") });
  if (modules.has("shop") && bootstrap?.features?.includes("shop.online")) nav.push({ label: t`Shop`, href: path("shop") });
  if (bootstrap?.makerspace.public_stats_enabled) nav.push({ label: t`Stats`, href: path("stats") });
  const support: { label: string; href: string; external?: boolean }[] = [];
  const email = bootstrap?.branding.support_email;
  if (email && /^[^\s@?&#:]+@[^\s@?&#:]+\.[^\s@?&#:]+$/.test(email)) support.push({ label: email, href: `mailto:${encodeURI(email)}` });
  try {
    const url = new URL(bootstrap?.branding.support_url ?? "");
    if (["https:", "http:"].includes(url.protocol) && !url.username && !url.password) support.push({ label: t`Contact support`, href: url.href, external: true });
  } catch { /* Legacy invalid support URLs do not become links. */ }
  return {
    makerspace: { slug, name, logo: bootstrap?.makerspace.logo_url || undefined, homeHref: path() }, nav,
    headerAction: { label: t`Sign in`, href: path("member") },
    liveStatus: <><MakerspaceMapLink makerspace={bootstrap?.makerspace} /><LanguageSwitcher /><ThemeToggle variant="icon" /></>,
    footer: { credit: "Powered by Space Works", links: [
      { label: t`About`, href: "/about" },
      { label: t`License`, href: LICENSE_URL, external: true },
      { label: t`Staff sign-in`, href: path("admin") },
      ...support,
    ] },
  };
}

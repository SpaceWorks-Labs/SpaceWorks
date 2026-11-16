import { t } from "@lingui/core/macro";
import { ThemeToggle } from "../../components/ThemeToggle";
import { LanguageSwitcher } from "../../components/shell/LanguageSwitcher";
import { MakerspaceMapLink } from "../../components/MakerspaceMapLink";
import type { TenantBootstrap } from "../../lib/api";
import { publicFamilies } from "../../lib/publicHome";
import { machineIntakeAvailable } from "./machineIntakeAvailability";

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
  if (machineIntakeAvailable(bootstrap, slug)) nav.push({ label: t`Request a job`, href: path("machine-jobs/new") });
  if (modules.has("shop") && bootstrap?.features?.includes("shop.online")) nav.push({ label: t`Shop`, href: path("shop") });
  if (bootstrap?.makerspace.public_stats_enabled) nav.push({ label: t`Stats`, href: path("stats") });
  // Decision 242(m): the bootstrap names a non-profit taking gifts; everyone else gets no Donate link.
  const donate = Boolean((bootstrap?.makerspace as { donate_enabled?: boolean } | undefined)?.donate_enabled);
  if (donate) nav.push({ label: t`Donate`, href: path("donate") });
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
      ...(donate ? [{ label: t`Support this space`, href: path("donate") }] : []),
      { label: t`About`, href: "/about" },
      { label: t`Privacy`, href: path("privacy") },
      { label: t`Terms`, href: path("terms") },
      { label: t`License`, href: LICENSE_URL, external: true },
      { label: t`Staff sign-in`, href: path("admin") },
      ...support,
    ] },
  };
}

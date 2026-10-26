import { ThemeToggle } from "../../components/ThemeToggle";
import { MakerspaceMapLink } from "../../components/MakerspaceMapLink";
import type { TenantBootstrap } from "../../lib/api";

export const LICENSE_URL = "https://github.com/SpaceWorks-Labs/SpaceWorks/blob/main/LICENSE";

/** Shared public navigation derives only from the bootstrap already loaded by its caller. */
export function publicPageChrome(slug: string, name: string, path: (part?: string) => string, bootstrap?: TenantBootstrap | null) {
  const modules = new Set(bootstrap?.modules ?? []);
  const nav = [{ label: "Catalogue", href: path() }];
  if (modules.has("events")) nav.push({ label: "Events", href: path("events") });
  if (modules.has("machines")) nav.push({ label: "Machines", href: path("machines") });
  if (modules.has("bookings")) nav.push({ label: "Book a space", href: path("bookings") });
  if (modules.has("printing")) nav.push({ label: "Request a 3D print", href: path("print") });
  if (bootstrap?.makerspace.public_stats_enabled) nav.push({ label: "Stats", href: path("stats") });
  const support: { label: string; href: string; external?: boolean }[] = [];
  const email = bootstrap?.branding.support_email;
  if (email && /^[^\s@?&#:]+@[^\s@?&#:]+\.[^\s@?&#:]+$/.test(email)) support.push({ label: email, href: `mailto:${encodeURI(email)}` });
  try {
    const url = new URL(bootstrap?.branding.support_url ?? "");
    if (["https:", "http:"].includes(url.protocol) && !url.username && !url.password) support.push({ label: "Contact support", href: url.href, external: true });
  } catch { /* Legacy invalid support URLs do not become links. */ }
  return {
    makerspace: { slug, name, logo: bootstrap?.makerspace.logo_url || undefined, homeHref: path() }, nav,
    headerAction: { label: "Sign in", href: path("member") },
    liveStatus: <><MakerspaceMapLink makerspace={bootstrap?.makerspace} /><ThemeToggle variant="icon" /></>,
    footer: { credit: "Powered by Space Works", links: [
      { label: "About", href: "/about" },
      { label: "License", href: LICENSE_URL, external: true },
      { label: "Staff sign-in", href: path("admin") },
      ...support,
    ] },
  };
}

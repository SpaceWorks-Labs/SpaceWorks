import type { TenantBootstrap } from "./api";

// Public/member colour overrides are page-scoped; keep the branding import surface stable.
export { readBrandTokens, tenantColourStyle } from "./brandColours";

const DEFAULT_FAVICON = "/brand/favicon.svg";

function setFavicon(url: string) {
  let link = document.querySelector<HTMLLinkElement>('link[data-spaceworks-favicon]')
    ?? document.querySelector<HTMLLinkElement>('link[rel="icon"]');
  if (!link) {
    link = document.createElement("link");
    link.rel = "icon";
    document.head.appendChild(link);
  }
  link.href = url;
  link.dataset.spaceworksFavicon = "";
  // A tenant logo may be any supported image format. Keep it after PNG fallbacks
  // so they cannot take precedence over the page's chosen favicon.
  link.removeAttribute("type");
  link.removeAttribute("sizes");
  document.head.appendChild(link);
}

export function applyTenantBranding(bootstrap: TenantBootstrap) {
  const name =
    bootstrap.branding.display_name ||
    bootstrap.makerspace.name ||
    "Space Works";
  // A routed page may have a more specific title (for example a public item).
  // Bootstrap also applies after child effects, so preserve that page's ownership.
  if (!document.head.querySelector("[data-spaceworks-page-metadata]")) document.title = name;
  if (typeof bootstrap.theme.logo_url === "string" && bootstrap.theme.logo_url) {
    setFavicon(bootstrap.theme.logo_url);
  } else {
    setFavicon(DEFAULT_FAVICON);
  }
}

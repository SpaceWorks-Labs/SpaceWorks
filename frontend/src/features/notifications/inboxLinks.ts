import { tenantPath } from "../../lib/tenant";

export function isInboxLink(value: string): boolean {
  return value.startsWith("/") && !value.startsWith("//") && !/[\\\x00-\x1f\x7f]/.test(value);
}

/** Saved notices can outlive a domain change or be opened on either frontend. */
export function inboxRoute(value: string, mode: "central" | "single", slug: string): string {
  if (!isInboxLink(value)) return "";
  const scoped = value.match(/^\/m\/([^/]+)(\/.*)?$/);
  if (scoped) {
    if (mode === "central") return value;
    // Never reinterpret another tenant's notice as a link into this tenant.
    return scoped[1] === slug ? tenantPath(mode, slug, scoped[2] || "") : "";
  }
  if (slug && /^\/(admin|member|items)([/?#]|$)/.test(value) && value !== "/member/archived") {
    return tenantPath(mode, slug, value);
  }
  return value;
}

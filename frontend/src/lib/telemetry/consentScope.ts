/** Consent follows the exact tenant and provider policy, never another space or configuration. */
export async function consentScope(tenantId: number, policy: unknown): Promise<string> {
  const bytes = new TextEncoder().encode(JSON.stringify(policy));
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  const hex = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, "0")).join("");
  return `${tenantId}:${hex}`;
}

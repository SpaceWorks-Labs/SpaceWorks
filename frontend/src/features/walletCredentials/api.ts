// Decision 223 (l), lane L4: wallet-pass signing credentials, per space and for the platform.
// Secrets are write-only; the server answers only whether each platform is configured.
import { staffRequest } from "../../lib/api";

export type Source = "space" | "platform" | "deployment" | null;
export type AppleStatus = { configured: boolean; pass_type_id?: string; team_id?: string; fingerprint?: string; expires_at?: string | null; expires_soon?: boolean };
export type GoogleStatus = { configured: boolean; issuer_id?: string; class_prefix?: string; fingerprint?: string };
export type WalletCredentials = { apple: AppleStatus; google: GoogleStatus; effective?: { apple: Source; google: Source };
  use_platform_credentials?: boolean;
  /** PATCH only: the Apple Pass Type ID changed, so passes already in wallets no longer update. */
  reissue_needed?: boolean };
export type WalletCredentialsInput = Partial<{
  apple_pass_type_id: string; apple_team_id: string; apple_p12: string; apple_p12_password: string;
  apple_cert_pem: string; apple_key_pem: string; apple_key_passphrase: string; apple_wwdr_pem: string;
  google_issuer_id: string; google_class_prefix: string; google_service_account: string;
  clear_apple: boolean; clear_google: boolean;
  /** Space scope only (decision 281): may the platform's credentials sign for this space when it has none. */
  use_platform_credentials: boolean;
}>;
export type WalletScope = { kind: "space"; makerspaceId: number } | { kind: "platform" };

const path = (scope: WalletScope) => scope.kind === "space"
  ? `/admin/makerspaces/${scope.makerspaceId}/wallet-credentials` : "/admin/platform/wallet-credentials";

export const walletKeys = {
  scope: (scope: WalletScope) => ["wallet-credentials", scope.kind === "space" ? scope.makerspaceId : "platform"] as const,
};

export const walletCredentialsApi = {
  read: (scope: WalletScope) => staffRequest<WalletCredentials>(path(scope)),
  save: (scope: WalletScope, input: WalletCredentialsInput) =>
    staffRequest<WalletCredentials>(path(scope), { method: "PATCH", body: JSON.stringify(input) }),
};

/** A binary .p12 file as base64, as the server expects it. */
export async function fileToBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (let at = 0; at < bytes.length; at += 0x8000) binary += String.fromCharCode(...bytes.subarray(at, at + 0x8000));
  return btoa(binary);
}

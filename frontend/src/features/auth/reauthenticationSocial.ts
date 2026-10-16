import { staffRequest } from "../../lib/api";
import type { ReauthenticationResult } from "./reauthenticationApi";

type Started = { authorization_url: string; state: string; nonce: string; expires_in: number };

export async function reauthenticateSocial(provider: string): Promise<ReauthenticationResult> {
  // Open synchronously from the user's click so the browser permits the popup.
  const popup = window.open("about:blank", "spaceworks-reauth", "popup,width=600,height=750");
  if (!popup) throw new Error("Allow the identity-provider popup to verify this browser session.");
  try {
    const started = await staffRequest<Started>("/auth/reauth/social/start", {
      method: "POST", body: JSON.stringify({ provider, redirect_uri: `${window.location.origin}/reauth/callback` }),
    });
    popup.location.href = started.authorization_url;
    const result = await new Promise<Record<string, string>>((resolve, reject) => {
      const deadline = Date.now() + 300_000;
      const timer = window.setInterval(() => {
        if (popup.closed || Date.now() > deadline) {
          window.clearInterval(timer);
          reject(new Error("Identity verification was cancelled or expired."));
          return;
        }
        try {
          if (popup.location.origin !== window.location.origin || popup.location.pathname !== "/reauth/callback") return;
          const query = new URLSearchParams(popup.location.search);
          const fragment = new URLSearchParams(popup.location.hash.replace(/^#/, ""));
          const state = query.get("state") || fragment.get("state") || "";
          if (!state) return;
          window.clearInterval(timer);
          if (state !== started.state || query.get("error") || fragment.get("error")) {
            reject(new Error("The identity provider refused verification."));
          } else resolve({ state, nonce: started.nonce, code: query.get("code") || "", id_token: fragment.get("id_token") || "" });
        } catch { /* The provider's cross-origin page remains inaccessible until it returns. */ }
      }, 250);
    });
    return await staffRequest<ReauthenticationResult>("/auth/reauth/social/complete", { method: "POST", body: JSON.stringify(result) });
  } finally { popup.close(); }
}

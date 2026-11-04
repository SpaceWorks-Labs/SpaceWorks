/** Loads Cloudflare Turnstile's script once, on demand (never on page load). */
export const TURNSTILE_SCRIPT_URL = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

export type TurnstileApi = {
  render: (container: HTMLElement, options: {
    sitekey: string; action?: string; theme?: "light" | "dark" | "auto";
    callback: (token: string) => void; "error-callback"?: () => void; "expired-callback"?: () => void;
  }) => string;
  remove: (widgetId: string) => void;
};

declare global {
  interface Window { turnstile?: TurnstileApi }
}

let loading: Promise<TurnstileApi> | null = null;

export function loadTurnstile(): Promise<TurnstileApi> {
  if (window.turnstile) return Promise.resolve(window.turnstile);
  if (loading) return loading;
  loading = new Promise<TurnstileApi>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = TURNSTILE_SCRIPT_URL;
    script.async = true;
    script.onload = () => window.turnstile ? resolve(window.turnstile) : reject(new Error("Turnstile did not start."));
    script.onerror = () => reject(new Error("Turnstile could not load."));
    document.head.appendChild(script);
  }).catch((error: Error) => { loading = null; throw error; });
  return loading;
}

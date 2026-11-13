import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { formatLocale } from "../../lib/format";
import { tenantDefaultMode } from "../../lib/useTenantBranding";
import { DisplayCanvas } from "./DisplayCanvas";
import { useDisplayScreen } from "./useDisplayScreen";
import type { DisplayTheme } from "./api";

/** Burn-in safety: the whole layout steps along a small loop every minute (a few px, never read as movement). */
const DRIFT = [[0, 0], [10, 6], [16, 0], [10, -6], [0, -10], [-10, -6], [-16, 0], [-10, 6]] as const;

/** `dark` is the original dark-room surface; `black` is true #000 for OLED; `brand` is dark with the space accent. */
export const THEME_CLASS: Record<DisplayTheme, string> = {
  dark: "sw-island-dark bg-bg text-ink", light: "bg-bg text-ink", black: "sw-island-dark bg-black text-ink",
  brand: "sw-island-dark bg-bg text-ink", space: "sw-island-dark bg-bg text-ink",
};

/** "Space default" follows the space's own look (tenantDefaultMode); "system" follows the screen's preference. */
export function resolveTheme(theme: DisplayTheme, spaceTheme: unknown): DisplayTheme {
  if (theme !== "space") return theme;
  const mode = tenantDefaultMode(spaceTheme);
  if (mode === "light") return "light";
  if (mode === "system" && typeof window.matchMedia === "function" && !window.matchMedia("(prefers-color-scheme: dark)").matches) return "light";
  return "dark";
}

function useNow(everyMs: number) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { const id = window.setInterval(() => setNow(Date.now()), everyMs); return () => window.clearInterval(id); }, [everyMs]);
  return now;
}

/**
 * /display: a TV or kiosk browser, including Anthias on a Raspberry Pi. It shows only the logged-out public
 * view of its space, needs no cookies or sign-in (the screen's secret is its own link), and never shows
 * Patch. Layout is fluid in rem-free Tailwind steps, so 1080p and 4K both fill the screen.
 */
export function SpaceDisplayPage() {
  const view = useDisplayScreen();
  const now = useNow(30_000);
  const [step, setStep] = useState(0);
  useEffect(() => { const id = window.setInterval(() => setStep((old) => (old + 1) % DRIFT.length), 60_000); return () => window.clearInterval(id); }, []);
  const [dx, dy] = DRIFT[step];
  const state = view.state;
  const paired = state?.state === "paired" ? state : null;
  const zone = paired?.space.timezone || "UTC";
  const clock = new Intl.DateTimeFormat(formatLocale(), { hour: "numeric", minute: "2-digit", timeZone: zone }).format(new Date(now));
  const theme = resolveTheme(paired?.config.theme ?? "dark", paired?.space.theme);
  return <main className={`${THEME_CLASS[theme]} min-h-screen p-10 2xl:p-16`} style={{ transform: `translate(${dx}px, ${dy}px)` }} aria-label={t`Space display`} data-theme-name={theme}>
    <header className="mb-10 flex items-center justify-between gap-6">
      <p className={`text-2xl font-semibold 2xl:text-4xl ${theme === "brand" ? "text-accent" : ""}`}>{paired ? paired.space.name : t`Space Works display`}</p>
      <p className="flex items-center gap-4 text-xl text-muted 2xl:text-3xl">
        {view.reconnecting ? <span role="status" className="rounded-full border border-warn px-3 py-1 text-warn-ink">{t`Reconnecting…`}</span> : null}
        <time className="tabular-nums" dateTime={new Date(now).toISOString()}>{clock}</time>
      </p>
    </header>
    {paired ? <DisplayCanvas state={paired} now={now} />
      : state?.state === "unclaimed" ? <section className="grid max-w-3xl gap-6" aria-labelledby="tv-pair">
        <h1 id="tv-pair" className="text-4xl font-semibold">{t`Pair this screen`}</h1>
        <p className="text-2xl text-muted">{t`In the staff console, open Settings, then Display screens, and enter this code.`}</p>
        <p aria-label={t`Pairing code`} className="font-mono text-8xl font-bold tracking-widest tabular-nums">{state.code}</p>
      </section>
        : <p role="status" className="text-3xl text-muted">{view.linkRevoked ? t`This screen address is no longer valid. Ask a manager for a new one.`
          : view.reset ? t`Getting a new pairing code…` : view.reconnecting ? t`Can't reach the server. Trying again…` : t`Starting…`}</p>}
  </main>;
}

import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { toast } from "../ui/toastStore";
import { eggsAllowed, useDelight } from "./DelightProvider";

// Easter-egg one-liners. Both sit behind the eggs flag and never run on kiosk, scanner,
// checkout or payment paths. "Once per session" is remembered in sessionStorage when it is
// available and in memory otherwise.
const SUDO_KEY = "sw.delight.sudo-make";
const LATE_KEY = "sw.delight.late-shift";
const seen = new Set<string>();
function once(key: string) {
  if (seen.has(key)) return false;
  try { if (window.sessionStorage.getItem(key)) { seen.add(key); return false; } } catch { /* storage blocked */ }
  return true;
}
function remember(key: string) {
  seen.add(key);
  try { window.sessionStorage.setItem(key, "1"); } catch { /* storage blocked */ }
}
const isSearch = (target: EventTarget | null): target is HTMLInputElement => target instanceof HTMLInputElement
  && (target.type === "search" || target.getAttribute("role") === "searchbox" || Boolean(target.closest("[role='search']")));

/** Typing `sudo make` into any search box answers "Okay." through the shared toast, once a session. */
export function SudoMake({ allowed }: { allowed: boolean }) {
  useEffect(() => {
    if (!allowed) return;
    const typed = (event: Event) => {
      if (!isSearch(event.target) || event.target.value.trim().toLowerCase() !== "sudo make" || !once(SUDO_KEY)) return;
      remember(SUDO_KEY);
      toast(t`Okay.`, { tone: "info", duration: 4000 });
    };
    document.addEventListener("input", typed, true);
    return () => document.removeEventListener("input", typed, true);
  }, [allowed]);
  return null;
}

/** A quiet, visible line on the staff dashboard between midnight and 4 am, local time, with a
 * keyboard-reachable dismiss that holds for the session. */
export function LateShiftLine({ now = new Date() }: { now?: Date }) {
  const { enabled, eggsEnabled } = useDelight();
  const [hidden, setHidden] = useState(() => !once(LATE_KEY));
  if (!enabled || !eggsEnabled || hidden || now.getHours() >= 4 || !eggsAllowed(window.location.pathname)) return null;
  return <p className="flex items-center gap-2 text-sm text-muted">
    <span>{t`Late shift? The solder's still warm.`}</span>
    <button type="button" aria-label={t`Dismiss`} className="inline-flex h-8 w-8 items-center justify-center rounded-full text-muted hover:bg-hover hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
      onClick={() => { remember(LATE_KEY); setHidden(true); }}><X size={14} aria-hidden="true" /></button>
  </p>;
}

// Seven logo clicks inside a rolling 4 s window open Maker mode. Most logos are links, and a click
// on one navigates (often a full page load), so the count lives in sessionStorage and a "pending"
// mark lets the page the user lands on open Maker mode. Every storage access is guarded: where
// storage is blocked the count falls back to memory and still works within one page.
const CLICKS = "sw.delight.logo-clicks";
const PENDING = "sw.delight.maker-pending";
const WINDOW_MS = 4000;
const NEEDED = 7;
let memory: { clicks: number[]; pending: number } = { clicks: [], pending: 0 };

function load(): typeof memory {
  try {
    const clicks = JSON.parse(window.sessionStorage.getItem(CLICKS) ?? "[]");
    const pending = Number(window.sessionStorage.getItem(PENDING) ?? 0);
    if (Array.isArray(clicks)) return { clicks: clicks.filter((value): value is number => typeof value === "number"), pending: Number.isFinite(pending) ? pending : 0 };
  } catch { /* storage blocked or unreadable: use memory */ }
  return memory;
}
function save(next: typeof memory) {
  memory = next;
  try {
    window.sessionStorage.setItem(CLICKS, JSON.stringify(next.clicks));
    if (next.pending) window.sessionStorage.setItem(PENDING, String(next.pending));
    else window.sessionStorage.removeItem(PENDING);
  } catch { /* storage blocked: memory already holds it */ }
}

/** Records one logo click; true on the seventh inside the window (which also marks Maker mode pending). */
export function countLogoClick(now = Date.now()) {
  const state = load();
  const clicks = [...state.clicks.filter(time => time <= now && now - time < WINDOW_MS), now];
  if (clicks.length >= NEEDED) { save({ clicks: [], pending: now }); return true; }
  save({ ...state, clicks });
  return false;
}

/** True while a seventh click is under four seconds old, for the page it led to. It is not cleared
 * on read, so React's development double-mount (and a quick second hop) still opens Maker mode. */
export function makerModePending(now = Date.now()) {
  const { pending } = load();
  return pending > 0 && pending <= now && now - pending < WINDOW_MS;
}

/** The user closed Maker mode: forget a pending open. */
export function clearMakerModePending() {
  const state = load();
  if (state.pending) save({ ...state, pending: 0 });
}

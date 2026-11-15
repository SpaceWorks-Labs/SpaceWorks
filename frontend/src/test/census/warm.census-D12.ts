import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { SRC } from "./source.census-D12";

// Route and staff-panel chunks are React.lazy imports. The first case to open a
// heavy chunk (the settings panel, the programme presentation tree) spends most of
// its admission wait transforming that module graph, so the cold case sees only its
// Suspense loader. Importing the same lazy targets once per worker, before any timed
// case, removes that cold-transform ordering effect. Nothing is mocked or replaced:
// the screens still load through their own lazy() calls at render time.
const LAZY_HOSTS = [
  "App.tsx", "AppRoutes.tsx", "AppRoutesLazyPages.tsx", "features/public/FamilyHome.tsx",
  "features/hub/LandingGate.tsx", "features/staff/StaffTabLoaders.tsx",
  "features/staff/platformConsole/platformConsolePages.ts", "features/staff/shop/ShopPanel.tsx",
];
export function lazyTargets() {
  const targets = new Set<string>();
  for (const host of LAZY_HOSTS) {
    const file = resolve(SRC, host);
    for (const match of readFileSync(file, "utf8").matchAll(/lazy\(\s*(?:async\s*)?\(\)\s*=>\s*import\(\s*["']([^"']+)["']/g))
      targets.add(resolve(dirname(file), match[1]));
  }
  return [...targets];
}
export async function warmLazyRoutes() {
  await Promise.all(lazyTargets().map(target => import(/* @vite-ignore */ target)));
}

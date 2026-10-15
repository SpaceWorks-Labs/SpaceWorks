import { AppRoutes } from "./AppRoutes";
import { lazy, Suspense } from "react";
import { Route, Routes, useLocation } from "react-router-dom";
import { CenteredCardLayout } from "./components/layouts";
import { LandingPage } from "./features/LandingPage";
import { useTenant } from "./lib/tenant";
const KioskStationPage = lazy(() => import("./features/kiosk/KioskStationPage").then((m) => ({ default: m.KioskStationPage })));

export default function App() {
  const tenant = useTenant();
  const { pathname } = useLocation();
  // Station UUID routes must open their precached shell even when no-store
  // config.js / tenant bootstrap cannot load. Central /kiosk/:slug stays distinct.
  if (/^\/m\/[^/]+\/kiosk\/[^/]+\/?$/.test(pathname)
      || /^\/kiosk\/[0-9a-f-]{36}\/?$/i.test(pathname)) {
    return <Suspense fallback={<div role="status"><CenteredCardLayout state={{ status: "loading" }} title="Loading kiosk…" body="" primary={{ label: "Loading…", disabled: true, disabledReason: "The kiosk is opening." }} /></div>}><Routes>
      <Route path="/kiosk/:stationToken" element={<KioskStationPage />} />
      <Route path="/m/:slug/kiosk/:stationToken" element={<KioskStationPage />} />
    </Routes></Suspense>;
  }
  // Do not gate this payment-only recovery route on archived tenant bootstrap: the tenant
  // screens below ("Loading site", "Site unavailable") are exactly what an archived member
  // must get past. Read the ROUTER's location, not `window.location` -- a client-side `Link`
  // updates router context without touching `window.location`, so a non-reactive read left
  // this branch stale and sent every click on the recovery CTA to the not-found page.
  if (tenant.mode === "single" && tenant.loading) {
    return <div role="status"><CenteredCardLayout state={{ status: "loading" }} title="Loading site…" body=""
      primary={{ label: "Loading…", disabled: true, disabledReason: "The site is opening." }} /></div>;
  }
  if (tenant.mode === "single" && tenant.error) {
    return <CenteredCardLayout state={{ status: "ready" }} media={{ icon: "TriangleAlert", tone: "danger" }}
      title="Site unavailable" body="The configured tenant could not be resolved."
      primary={{ label: "Retry", onClick: () => window.location.reload() }} />;
  }
  return <AppRoutes mode={tenant.mode} landing={<LandingPage />} />;
}

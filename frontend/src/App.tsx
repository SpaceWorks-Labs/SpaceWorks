import { ProgrammeDelight } from "./features/events/programme/ProgrammeDelight";
import { ReauthenticationDialog } from "./features/auth/ReauthenticationDialog";
import { ReauthenticationReturn } from "./features/auth/ReauthenticationReturn";
import { AppRoutes } from "./AppRoutes";
import { lazy, Suspense } from "react";
import { Route, Routes, useLocation } from "react-router-dom";
import { CenteredCardLayout } from "./components/layouts";
import { LandingPage } from "./features/LandingPage";
import { PausedSpacePage } from "./features/platformNotices/PausedSpacePage";
import { useTenant } from "./lib/tenant";
const KioskStationPage = lazy(() => import("./features/kiosk/KioskStationPage").then((m) => ({ default: m.KioskStationPage })));
// Explicit test dev mode only: Vite removes this import and route from production builds.
const ChartTestPage = import.meta.env.DEV && import.meta.env.MODE === "chart-test"
  ? lazy(() => import("./features/staff/panels/charts/ChartTestPage")) : null;

export default function App() {
  const tenant = useTenant();
  const { pathname } = useLocation();
  if (ChartTestPage && pathname === "/__test/charts") return <Suspense fallback={<p role="status">Loading chart fixture…</p>}><ChartTestPage /></Suspense>;
  if (pathname === "/reauth/callback" || pathname === "/reauth/confirm") return <ReauthenticationReturn confirmation={pathname === "/reauth/confirm"} />;
  if (pathname === "/account/restore" || pathname === "/member/archived") {
    return <><AppRoutes mode={tenant.mode} landing={null} /><ReauthenticationDialog /></>;
  }
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
  const accountUtility = /^\/(?:m\/[^/]+\/)?member\/account\/(?:saved-details|security-activity)\/?$/.test(pathname);
  if (!accountUtility && tenant.mode === "single" && tenant.loading) {
    return <div role="status"><CenteredCardLayout state={{ status: "loading" }} title="Loading site…" body=""
      primary={{ label: "Loading…", disabled: true, disabledReason: "The site is opening." }} /></div>;
  }
  if (!accountUtility && tenant.mode === "single" && (tenant.error as { code?: string } | null)?.code === "space_paused") {
    return <PausedSpacePage primary={{ label: "Retry", onClick: () => window.location.reload() }} />;
  }
  if (!accountUtility && tenant.mode === "single" && tenant.error) {
    return <CenteredCardLayout state={{ status: "ready" }} media={{ icon: "TriangleAlert", tone: "danger" }}
      title="Site unavailable" body="The configured tenant could not be resolved."
      primary={{ label: "Retry", onClick: () => window.location.reload() }} />;
  }
  return <ProgrammeDelight><AppRoutes mode={tenant.mode} landing={<LandingPage />} /><ReauthenticationDialog /></ProgrammeDelight>;
}

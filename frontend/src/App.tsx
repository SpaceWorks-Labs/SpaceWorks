import { t } from "@lingui/core/macro";
import { LogoLoader } from "./components/LogoLoader";
import { ProgrammeDelight } from "./features/events/programme/ProgrammeDelight";
import { ReauthenticationDialog } from "./features/auth/ReauthenticationDialog";
import { ChooseUsernameGate } from "./features/profile/username/ChooseUsernameGate";
import { ReauthenticationReturn } from "./features/auth/ReauthenticationReturn";
import { GITHUB_APP_CALLBACK_PATH, GithubAppCallbackPage } from "./features/auth/GithubAppCallbackPage";
import { AppRoutes } from "./AppRoutes";
import { lazy, Suspense } from "react";
import { Route, Routes, useLocation } from "react-router-dom";
import { CenteredCardLayout } from "./components/layouts";
import { PausedSpacePage } from "./features/platformNotices/PausedSpacePage";
import { isAccountUtilityPath } from "./lib/accountUtilityPaths";
import { useTenant } from "./lib/tenant";
import { LandingGate } from "./features/hub/LandingGate";
// The hub front page is its own chunk: single-tenant installs never download it.
const HubLandingPage = lazy(() => import("./features/hub/HubLandingPage").then(m => ({ default: m.HubLandingPage })));
const FirebaseBridgePage = lazy(() => import("./features/notifications/firebase/FirebaseBridgePage").then(m => ({ default: m.FirebaseBridgePage })));
const KioskStationPage = lazy(() => import("./features/kiosk/KioskStationPage").then((m) => ({ default: m.KioskStationPage })));
// Explicit test dev mode only: Vite removes this import and route from production builds.
const ChartTestPage = import.meta.env.DEV && import.meta.env.MODE === "chart-test"
  ? lazy(() => import("./features/staff/panels/charts/ChartTestPage")) : null;

export default function App() {
  const tenant = useTenant();
  const { pathname } = useLocation();
  if (pathname === "/firebase-alerts/setup") return <Suspense fallback={<LogoLoader label={t`Loading notifications…`} />}><FirebaseBridgePage /></Suspense>;
  if (ChartTestPage && pathname === "/__test/charts") return <Suspense fallback={<LogoLoader label={t`Loading chart fixture…`} />}><ChartTestPage /></Suspense>;
  if (pathname === "/reauth/callback" || pathname === "/reauth/confirm") return <ReauthenticationReturn confirmation={pathname === "/reauth/confirm"} />;
  // Decision 361: GitHub's native app-link redirect opened in a browser; no tenant bootstrap needed.
  if (pathname === GITHUB_APP_CALLBACK_PATH) return <GithubAppCallbackPage />;
  if (pathname === "/account/restore" || pathname === "/member/archived") {
    return <><AppRoutes mode={tenant.mode} landing={null} /><ReauthenticationDialog /></>;
  }
  // Station UUID routes must open their precached shell even when no-store
  // config.js / tenant bootstrap cannot load. Central /kiosk/:slug stays distinct.
  if (/^\/m\/[^/]+\/kiosk\/[^/]+\/?$/.test(pathname)
      || /^\/kiosk\/[0-9a-f-]{36}\/?$/i.test(pathname)) {
    return <Suspense fallback={<LogoLoader label={t`Loading kiosk…`} className="min-h-dvh content-center" />}><Routes>
      <Route path="/kiosk/:stationToken" element={<KioskStationPage />} />
      <Route path="/m/:slug/kiosk/:stationToken" element={<KioskStationPage />} />
    </Routes></Suspense>;
  }
  // Do not gate this payment-only recovery route on archived tenant bootstrap: the tenant
  // screens below ("Loading site", "Site unavailable") are exactly what an archived member
  // must get past. Read the ROUTER's location, not `window.location` -- a client-side `Link`
  // updates router context without touching `window.location`, so a non-reactive read left
  // this branch stale and sent every click on the recovery CTA to the not-found page.
  const accountUtility = isAccountUtilityPath(pathname);
  if (!accountUtility && tenant.mode === "single" && tenant.loading) {
    return <LogoLoader label={t`Loading site…`} className="min-h-dvh content-center" />;
  }
  if (!accountUtility && tenant.mode === "single" && (tenant.error as { code?: string } | null)?.code === "space_paused") {
    return <PausedSpacePage primary={{ label: t`Retry`, onClick: () => window.location.reload() }} />;
  }
  if (!accountUtility && tenant.mode === "single" && tenant.error) {
    return <CenteredCardLayout state={{ status: "ready" }} media={{ icon: "TriangleAlert", tone: "danger" }}
      title={t`Site unavailable`} body={t`This makerspace address could not be found. Check the link, or ask the person who runs the site.`}
      primary={{ label: t`Retry`, onClick: () => window.location.reload() }} />;
  }
  return <ProgrammeDelight><AppRoutes mode={tenant.mode} landing={<LandingGate landing={<HubLandingPage />} />} /><ReauthenticationDialog /><ChooseUsernameGate /></ProgrammeDelight>;
}

// Phase 8 i18n: activates the catalogue before any module that renders text is evaluated.
import "./lib/i18n";
import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { WebTelemetry } from "./components/WebTelemetry";
import { installSessionTelemetryFence } from "./lib/telemetry/sessionFence";
import { fenceWebTelemetry, installWebTelemetryBoundary } from "./lib/telemetry/runtime";
import { installAnalyticsNavigationGuard } from "./lib/webAnalytics";
import { PwaRegistration } from "./components/PwaRegistration";
import { ToastHost } from "./components/ui/ToastHost";
import "./index.css";
import { cleanupLegacyAccessToken } from "./lib/api";
import { queryClient } from "./lib/queryClient";
import { I18nRoot } from "./lib/I18nRoot";
import { installLocaleFetch } from "./lib/localeFetch";
import { TenantProvider } from "./lib/tenant";
import { SessionBoundary } from "./lib/SessionBoundary";
import { initializeTheme } from "./lib/theme";
import { pruneExpiredOfflineStates } from "./features/staff/eventCheckInOfflineStore";
import { listQueues } from "./features/kiosk/offlineQueueStore";
import { replayQueue } from "./features/kiosk/kioskReplayClient";

installLocaleFetch();
installAnalyticsNavigationGuard();
installWebTelemetryBoundary();
installSessionTelemetryFence(fenceWebTelemetry);
initializeTheme();
cleanupLegacyAccessToken();
void pruneExpiredOfflineStates().catch(() => undefined);
void listQueues().then(async (queues) => {
  for (const queue of queues) await replayQueue(queue.scope);
}).catch(() => undefined);

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <I18nRoot queryClient={queryClient}>
    <QueryClientProvider client={queryClient}>
      <TenantProvider>
        <BrowserRouter>
          <SessionBoundary>
          <WebTelemetry />
          <PwaRegistration />
          <ToastHost />
          <App />
          </SessionBoundary>
        </BrowserRouter>
      </TenantProvider>
    </QueryClientProvider>
    </I18nRoot>
  </React.StrictMode>,
);

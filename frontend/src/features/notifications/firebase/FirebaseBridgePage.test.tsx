import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
const mocks = vi.hoisted(() => ({ begin: vi.fn(), dispose: vi.fn() }));
vi.mock("../../../lib/api", () => ({ memberRequest: async () => ({ configured: true, config: { api_key: "x", auth_domain: "x", project_id: "x", app_id: "x", messaging_sender_id: "x", vapid_public_key: "x" } }) }));
vi.mock("./firebaseBridge", () => ({ beginFirebaseBridge: mocks.begin, disableFirebaseForSpace: vi.fn() }));
vi.mock("./firebaseRegistration", () => ({ registerOwnFirebaseWorker: async () => ({ active: { scriptURL: "same" } }) }));
import { FirebaseBridgePage } from "./FirebaseBridgePage";
it("disposes a handle that arrives after the setup page unmounts", async () => {
  let complete!: (value: { dispose: () => void }) => void; mocks.begin.mockReturnValue(new Promise(resolve => { complete = resolve; })); mocks.dispose.mockClear();
  history.replaceState(null, "", "/firebase-alerts/setup?space=7"); vi.stubGlobal("Notification", { requestPermission: async () => "granted" }); vi.stubGlobal("navigator", { serviceWorker: { controller: { scriptURL: "same" } } });
  try { const view = render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><FirebaseBridgePage /></QueryClientProvider>);
    fireEvent.click(await screen.findByText("Enable notifications")); await waitFor(() => expect(mocks.begin).toHaveBeenCalled()); view.unmount(); complete({ dispose: mocks.dispose }); await waitFor(() => expect(mocks.dispose).toHaveBeenCalledOnce());
  } finally { vi.unstubAllGlobals(); }
});

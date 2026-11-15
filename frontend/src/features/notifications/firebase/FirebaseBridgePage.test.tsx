import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
const CONFIG = { configured: true, config: { api_key: "x", auth_domain: "x", project_id: "x", app_id: "x", messaging_sender_id: "x", vapid_public_key: "x" } };
const mocks = vi.hoisted(() => ({ begin: vi.fn(), dispose: vi.fn(), config: vi.fn() }));
vi.mock("../../../lib/api", () => ({ memberRequest: mocks.config }));
vi.mock("./firebaseBridge", () => ({ beginFirebaseBridge: mocks.begin, disableFirebaseForSpace: vi.fn() }));
vi.mock("./firebaseRegistration", () => ({ registerOwnFirebaseWorker: async () => ({ active: { scriptURL: "same" } }) }));
import { FirebaseBridgePage } from "./FirebaseBridgePage";
beforeEach(() => { mocks.config.mockReset(); mocks.config.mockResolvedValue(CONFIG); history.replaceState(null, "", "/firebase-alerts/setup?space=7"); });
const mount = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><FirebaseBridgePage /></QueryClientProvider>);
it("shows web push switched off for the space (404) as unavailable, with no Retry", async () => {
  mocks.config.mockRejectedValue(Object.assign(new Error("Not found."), { status: 404 }));
  mount();
  expect(await screen.findByText("Browser notifications are unavailable for this space.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /retry/i })).not.toBeInTheDocument();
});
it("offers Retry for a server-side failure loading the config", async () => {
  mocks.config.mockRejectedValueOnce(Object.assign(new Error("Service unavailable."), { status: 503 }));
  mount();
  fireEvent.click(await screen.findByRole("button", { name: /retry/i }));
  expect(await screen.findByText("Enable notifications")).toBeInTheDocument();
});
it("disposes a handle that arrives after the setup page unmounts", async () => {
  let complete!: (value: { dispose: () => void }) => void; mocks.begin.mockReturnValue(new Promise(resolve => { complete = resolve; })); mocks.dispose.mockClear();
  history.replaceState(null, "", "/firebase-alerts/setup?space=7"); vi.stubGlobal("Notification", { requestPermission: async () => "granted" }); vi.stubGlobal("navigator", { serviceWorker: { controller: { scriptURL: "same" } } });
  try { const view = render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><FirebaseBridgePage /></QueryClientProvider>);
    fireEvent.click(await screen.findByText("Enable notifications")); await waitFor(() => expect(mocks.begin).toHaveBeenCalled()); view.unmount(); complete({ dispose: mocks.dispose }); await waitFor(() => expect(mocks.dispose).toHaveBeenCalledOnce());
  } finally { vi.unstubAllGlobals(); }
});

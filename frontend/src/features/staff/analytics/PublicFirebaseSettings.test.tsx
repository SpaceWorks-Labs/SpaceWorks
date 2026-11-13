import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
const api = vi.hoisted(() => vi.fn());
vi.mock("../../../lib/api", () => ({ staffRequest: api, StructuredApiError: class extends Error {} }));
import { PublicFirebaseSettings } from "./PublicFirebaseSettings";
const config = { api_key: "key", auth_domain: "", project_id: "project", app_id: "app", messaging_sender_id: "123", measurement_id: "", vapid_public_key: "public" };
function mount() { return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}><PublicFirebaseSettings /></QueryClientProvider>); }
beforeEach(() => { api.mockReset(); });
it("loads public configuration and saves the complete envelope through staffRequest", async () => {
  api.mockResolvedValue({ configured: true, config }); mount();
  expect(await screen.findByDisplayValue("project")).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Firebase project ID"), { target: { value: "new-project" } });
  fireEvent.click(screen.getByText("Save Firebase web settings"));
  await waitFor(() => expect(api).toHaveBeenCalledWith("/admin/platform/firebase-web-settings", { method: "PATCH", body: JSON.stringify({ config: { ...config, project_id: "new-project" } }) }));
});
it("requires mandatory public fields and surfaces a server validation failure", async () => {
  api.mockResolvedValueOnce({ configured: false, config: null }); mount();
  expect((await screen.findByText("Save Firebase web settings") as HTMLButtonElement).disabled).toBe(true);
  for (const [label, value] of [["Web API key", "key"], ["Firebase project ID", "project"], ["Web app ID", "app"], ["Messaging sender ID", "123"], ["VAPID public key", "public"]]) fireEvent.change(screen.getByLabelText(label), { target: { value } });
  api.mockRejectedValueOnce(new Error("invalid VAPID")); fireEvent.click(screen.getByText("Save Firebase web settings"));
  expect(await screen.findByRole("alert")).toBeTruthy();
});
it("uses the shared staff request path for reauthentication and reports a rejected write", async () => {
  api.mockResolvedValueOnce({ configured: true, config }); mount(); await screen.findByDisplayValue("project");
  api.mockRejectedValueOnce(new Error("reauthentication required")); fireEvent.click(screen.getByText("Save Firebase web settings"));
  expect(await screen.findByRole("alert")).toBeTruthy();
  expect(api).toHaveBeenCalledWith("/admin/platform/firebase-web-settings", expect.objectContaining({ method: "PATCH" }));
});

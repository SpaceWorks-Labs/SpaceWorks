import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
const mocks = vi.hoisted(() => ({ mutate: vi.fn(), data: { config: { pageview: { provider: "ga4", site_id: "G-OLD", endpoint: "" }, replay: { provider: "none", site_id: "", endpoint: "" }, diagnostics: { sentry: { enabled: false, dsn: "", sample_rate: 1 }, firebase_performance: { enabled: false, sample_rate: 0.1 } }, firebase: { api_key: "", auth_domain: "", project_id: "", app_id: "", messaging_sender_id: "", measurement_id: "G-NEW", vapid_public_key: "" } } } }));
vi.mock("./telemetryApi", () => ({ useWebTelemetry: () => ({ query: { data: mocks.data }, save: { mutate: mocks.mutate, isPending: false } }) }));
import { WebTelemetrySettings } from "./WebTelemetrySettings";
it("uses the Firebase measurement field and clears the former generic ID", async () => {
  mocks.mutate.mockClear(); render(<WebTelemetrySettings scope={{ kind: "platform" }} />);
  fireEvent.change(await screen.findByLabelText("Page analytics"), { target: { value: "firebase" } });
  expect(screen.queryByLabelText("Site or measurement ID")).toBeNull(); expect((screen.getByLabelText("Measurement ID") as HTMLInputElement).value).toBe("G-NEW");
  fireEvent.click(screen.getByText("Save web telemetry")); await waitFor(() => expect(mocks.mutate).toHaveBeenCalledWith(expect.objectContaining({ pageview: expect.objectContaining({ provider: "firebase", site_id: "" }), firebase: expect.objectContaining({ measurement_id: "G-NEW" }) })));
});
it("retains the generic measurement field for GA4 and presents readable Firebase labels", async () => {
  render(<WebTelemetrySettings scope={{ kind: "platform" }} />); expect((await screen.findByLabelText("Site or measurement ID") as HTMLInputElement).value).toBe("G-OLD");
  for (const label of ["API key", "Auth domain", "Project ID", "App ID", "Messaging sender ID", "Measurement ID", "VAPID public key"]) expect(screen.getByLabelText(label)).toBeTruthy();
});

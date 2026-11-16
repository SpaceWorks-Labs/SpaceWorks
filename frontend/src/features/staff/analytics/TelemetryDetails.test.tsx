import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { expect, it } from "vitest";
import { TelemetryDetails } from "./TelemetryDetails";
import type { WebTelemetryConfig } from "./telemetryApi";
const defaults: WebTelemetryConfig = { pageview: { provider: "none", site_id: "", endpoint: "" }, replay: { provider: "none", site_id: "", endpoint: "" }, diagnostics: { sentry: { enabled: false, dsn: "", sample_rate: 1 }, firebase_performance: { enabled: false, sample_rate: 0.1 } }, firebase: { api_key: "", auth_domain: "", project_id: "", app_id: "", messaging_sender_id: "", measurement_id: "", vapid_public_key: "" } };
function Form() { const [value, setValue] = useState(defaults); return <TelemetryDetails value={value} onChange={setValue} />; }
it("retains useful sampling defaults with both diagnostics disabled", () => {
  render(<Form />); expect((screen.getByLabelText("Sentry errors") as HTMLInputElement).checked).toBe(false); expect((screen.getByLabelText("Firebase performance") as HTMLInputElement).checked).toBe(false);
  expect((screen.getByLabelText("Sentry sample rate") as HTMLInputElement).value).toBe("1"); expect((screen.getByLabelText("Performance sample rate") as HTMLInputElement).value).toBe("0.1");
});
it("retains an explicit zero and explains that enabled diagnostics send no events", () => {
  render(<Form />); fireEvent.click(screen.getByLabelText("Sentry errors")); fireEvent.click(screen.getByLabelText("Firebase performance"));
  fireEvent.change(screen.getByLabelText("Sentry sample rate"), { target: { value: "0" } }); fireEvent.change(screen.getByLabelText("Performance sample rate"), { target: { value: "0" } });
  expect((screen.getByLabelText("Sentry sample rate") as HTMLInputElement).value).toBe("0"); expect((screen.getByLabelText("Performance sample rate") as HTMLInputElement).value).toBe("0"); expect(screen.getAllByText(/0% sampling/)).toHaveLength(2);
});

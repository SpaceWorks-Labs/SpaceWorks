import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { CertificatePublicationControls } from "./CertificatePublicationControls";

const request = vi.hoisted(() => vi.fn());
vi.mock("../../../lib/api", () => ({ staffRequest: request }));
beforeEach(() => { request.mockReset(); request.mockResolvedValue({ enabled: false, event_version: 4 }); });

it("requires explicit historical IDs and submits event-only publication consent", async () => {
  render(<QueryClientProvider client={new QueryClient()}><CertificatePublicationControls eventId={42} /></QueryClientProvider>);
  const button = screen.getByRole("button", { name: "Apply verification policy" });
  await waitFor(() => expect(button).toBeEnabled());
  fireEvent.change(screen.getByLabelText(/Optional existing certificate IDs/), { target: { value: "10,11" } });
  fireEvent.click(screen.getByRole("checkbox")); fireEvent.click(button);
  await waitFor(() => expect(request.mock.calls.some((row) => row[1]?.method === "POST")).toBe(true));
  const call = request.mock.calls.find((row) => row[1]?.method === "POST")!;
  expect(JSON.parse(call[1].body)).toMatchObject({ enabled: true, certificate_ids: [10, 11], expected_version: 4 });
});

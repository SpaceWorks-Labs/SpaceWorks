import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/api", async (original) => ({ ...await original<object>(), staffRequest: request }));

import type { NotificationDestination } from "../notificationDestinationTypes";
import { DestinationForm } from "./DestinationForm";
import { DestinationRow } from "./DestinationRow";

const options = { machineTypes: [], machines: [], categories: [] };
const webhook: NotificationDestination = { id: 9, channel: "webhook", label: "Ops hook", telegram_chat_id: "", is_active: true,
  payload_version: 2, credential_set: true, signing_secret_set: true, scope: { machine_type_ids: [], machine_ids: [], category_ids: [] },
  created_at: "2026-11-01T00:00:00Z", updated_at: "2026-11-01T00:00:00Z" };
const wrap = (ui: JSX.Element) => <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{ui}</QueryClientProvider>;

beforeEach(() => { request.mockReset(); });

describe("webhook signing secret (parity A10)", () => {
  it("shows the generated secret once after creating a room, then never again", async () => {
    request.mockResolvedValue({ ...webhook, signing_secret: "whsec_generated_0123456789" });
    const onDone = vi.fn();
    render(wrap(<DestinationForm basePath="/admin/makerspace/3/notification-destinations" channels={[{ key: "webhook", label: "Signed webhook" }]}
      makerspaceId={3} onDone={onDone} options={options as never} />));
    fireEvent.change(screen.getByPlaceholderText("Laser team"), { target: { value: "Ops hook" } });
    fireEvent.change(screen.getByPlaceholderText("https://hooks.example.com/…"), { target: { value: "https://hooks.example.org/x" } });
    expect(screen.getByPlaceholderText("Leave blank to generate one")).not.toBeRequired();
    fireEvent.click(screen.getByRole("button", { name: "Save room" }));
    expect(await screen.findByTestId("signing-secret")).toHaveTextContent("whsec_generated_0123456789");
    expect(screen.getByText("Copy this signing secret now.")).toBeVisible();
    const body = JSON.parse(request.mock.calls[0][1].body);
    expect(body).not.toHaveProperty("signing_secret");
    expect(onDone).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "I've saved it" }));
    expect(onDone).toHaveBeenCalledTimes(1);
  });

  it("closes straight away when the server generated nothing (a typed secret or another channel)", async () => {
    request.mockResolvedValue({ ...webhook, channel: "slack", signing_secret_set: false });
    const onDone = vi.fn();
    render(wrap(<DestinationForm basePath="/b" channels={[{ key: "slack", label: "Slack" }]} makerspaceId={3} onDone={onDone} options={options as never} />));
    fireEvent.change(screen.getByPlaceholderText("Laser team"), { target: { value: "Room" } });
    fireEvent.click(screen.getByRole("button", { name: "Save room" }));
    await waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(screen.queryByTestId("signing-secret")).toBeNull();
  });

  it("rotates with a grace period and reveals the new secret once", async () => {
    request.mockResolvedValue({ destination: webhook, signing_secret: "whsec_rotated_abcdefghijkl", previous_valid_until: "2026-11-12T10:00:00Z" });
    render(wrap(<DestinationRow basePath="/admin/makerspace/3/notification-destinations" destination={webhook} makerspaceId={3} onDelete={vi.fn()} options={options as never} />));
    fireEvent.click(screen.getByRole("button", { name: "Actions for Ops hook" }));
    fireEvent.click(await screen.findByRole("menuitem", { name: /Rotate signing secret/ }));
    const hours = screen.getByLabelText(/Keep the old secret working for/);
    fireEvent.change(hours, { target: { value: "200" } });
    expect(screen.getByRole("button", { name: "Rotate secret" })).toBeDisabled();
    fireEvent.change(hours, { target: { value: "6" } });
    fireEvent.click(screen.getByRole("button", { name: "Rotate secret" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/makerspace/3/notification-destinations/9/rotate-secret",
      { method: "POST", body: JSON.stringify({ grace_hours: 6 }) }));
    expect(await screen.findByTestId("signing-secret")).toHaveTextContent("whsec_rotated_abcdefghijkl");
    expect(screen.getByText(/previous secret keeps working until/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "I've saved it" }));
    expect(screen.queryByTestId("signing-secret")).toBeNull();
  });

  it("offers no rotation on a chat room", () => {
    render(wrap(<DestinationRow basePath="/b" destination={{ ...webhook, channel: "slack" }} makerspaceId={3} onDelete={vi.fn()} options={options as never} />));
    fireEvent.click(screen.getByRole("button", { name: "Actions for Ops hook" }));
    expect(screen.queryByRole("menuitem", { name: /Rotate signing secret/ })).toBeNull();
  });
});

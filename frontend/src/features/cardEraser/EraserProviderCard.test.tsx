import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { staffRequest } from "../../lib/api";
import { eraserErrorText } from "./api";
import { EraserProviderCard } from "./EraserProviderCard";
import { eraserSettingsSections } from "./eraserSettingsSection";

vi.mock("../../lib/api", async (original) => ({ ...(await original<typeof import("../../lib/api")>()), staffRequest: vi.fn() }));

const show = (scope: Parameters<typeof EraserProviderCard>[0]["scope"]) =>
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><EraserProviderCard scope={scope} /></QueryClientProvider>);
const status = { configured: true, provider_url: "https://eraser.example.org", fingerprint: "abc123def456", last_test_at: null,
  last_test_ok: null, last_test_error: "", use_platform_provider: true, platform_available: true, effective: "space" as const };

describe("EraserProviderCard", () => {
  beforeEach(() => { vi.mocked(staffRequest).mockReset(); });

  it("shows the address and a fingerprint, never the secret, and says which service the space uses", async () => {
    vi.mocked(staffRequest).mockResolvedValue(status);
    show({ kind: "space", makerspaceId: 3 });
    expect(await screen.findByText(/https:\/\/eraser\.example\.org/)).toBeVisible();
    expect(screen.getByText("Using this space's own service.")).toBeVisible();
    expect(screen.queryByLabelText("Shared secret")).not.toBeInTheDocument();
    expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/3/image-adapter");
  });

  it("saves the address and secret with a PATCH and needs a 16 character secret", async () => {
    vi.mocked(staffRequest).mockResolvedValueOnce({ ...status, configured: false, provider_url: "", fingerprint: "" }).mockResolvedValue(status);
    show({ kind: "platform" });
    fireEvent.click(await screen.findByRole("button", { name: "Add service" }));
    fireEvent.change(screen.getByLabelText("Service address"), { target: { value: "http://bg-eraser:8080" } });
    fireEvent.change(screen.getByLabelText("Shared secret"), { target: { value: "short" } });
    expect(screen.getByRole("button", { name: "Save service" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Shared secret"), { target: { value: "a-long-enough-secret-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Save service" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/platform/image-adapter", { method: "PATCH",
      body: JSON.stringify({ provider_url: "http://bg-eraser:8080", secret: "a-long-enough-secret-1" }) }));
  });

  it("tests the connection and explains a typed failure", async () => {
    vi.mocked(staffRequest).mockResolvedValueOnce(status)
      .mockResolvedValueOnce({ ok: false, error: "invalid_signature", tested_at: "2026-11-11T10:00:00Z" }).mockResolvedValue(status);
    show({ kind: "space", makerspaceId: 3 });
    fireEvent.click(await screen.findByRole("button", { name: "Test connection" }));
    expect(await screen.findByText(/rejected our signature/)).toBeVisible();
    expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/3/image-adapter/test", { method: "POST" });
  });

  it("removes the service and lets a space opt out of the platform's", async () => {
    vi.mocked(staffRequest).mockResolvedValue(status);
    show({ kind: "space", makerspaceId: 3 });
    fireEvent.click(await screen.findByRole("checkbox", { name: /Use the platform's service/ }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/3/image-adapter",
      { method: "PATCH", body: JSON.stringify({ use_platform_provider: false }) }));
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/3/image-adapter",
      { method: "PATCH", body: JSON.stringify({ clear: true }) }));
  });

  it("appears in settings only for a Space Manager while the switch is on", () => {
    const on = { id: 3, enabled_features: ["cards.photo_cutout"], enabled_modules: ["membership"] };
    expect(eraserSettingsSections(on, true)).toHaveLength(1);
    expect(eraserSettingsSections(on, false)).toHaveLength(0);
    expect(eraserSettingsSections({ id: 3, enabled_features: [], enabled_modules: ["membership"] }, true)).toHaveLength(0);
  });

  it("words every typed error code", () => {
    for (const code of ["invalid_signature", "provider_unreachable", "no_subject_found", "response_no_alpha", "url_not_allowed"])
      expect(eraserErrorText(code)).not.toBe("");
    expect(eraserErrorText("")).toBe("");
  });
});

import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api";
import { MyNotificationSettings } from "./MyNotificationSettings";
import type { Selection } from "./channelsApi";

const h = vi.hoisted(() => ({
  preferences: { isLoading: false, error: null as Error | null, data: { preferences: [] as Selection[] }, refetch: vi.fn() },
  save: { mutate: vi.fn(), isPending: false, isSuccess: false, error: null as Error | null },
  verify: { mutate: vi.fn(), isError: false, isSuccess: false }, install: { mutate: vi.fn(), isError: false, isSuccess: false },
}));
vi.mock("./channelsApi", () => ({ usePreferences: () => h.preferences,
  useEndpoints: () => ({ data: { results: [] } }), useOAuthReturn: () => ({}),
  useVerifyChallenge: () => h.verify, useSavePreferences: () => h.save }));
vi.mock("./smsConsentApi", () => ({ useSmsConsent: () => ({ data: undefined }) }));
vi.mock("./SlackInstallation", () => ({ slackInstallKey: () => "slack-install:4", useCompleteSlackInstall: () => h.install }));
vi.mock("./SmsConsent", () => ({ SmsConsent: () => null }));
vi.mock("./PersonalChannels", () => ({ PersonalChannels: () => null, connectedChannels: () => new Set() }));
vi.mock("./ChannelDeliveryLog", () => ({ ChannelDeliveryLog: () => null }));

function show() {
  return render(<MemoryRouter><MyNotificationSettings makerspaceId={4} member /></MemoryRouter>);
}

beforeEach(() => {
  h.preferences.error = null;
  h.preferences.data = { preferences: [{ category: "payments", channels: ["email"], email_fallback: false,
    available_channels: ["email", "telegram"] }] };
  h.preferences.refetch.mockReset(); h.save.mutate.mockReset();
  h.save.error = null; h.save.isPending = false; h.save.isSuccess = false;
});

describe("personal notification settings preserve real preference controls", () => {
  it("module-off refuses the whole form, and restoring it offers the server's retained selections", () => {
    h.preferences.error = new StructuredApiError(404, { code: "module_disabled", detail: "Notifications are off." });
    const view = show();
    expect(screen.getByRole("alert")).toHaveTextContent("Notifications are off.");
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    h.preferences.error = null;
    view.rerender(<MemoryRouter><MyNotificationSettings makerspaceId={4} member /></MemoryRouter>);
    expect(screen.getByRole("checkbox", { name: "Payments: Email" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Payments: Telegram" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Save choices" })).toBeDisabled();
  });

  it("empty server preferences explain why there is no editable form", () => {
    h.preferences.data = { preferences: [] };
    show();
    expect(screen.getByText("There are no notifications to choose channels for in this space yet.")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Save choices" })).not.toBeInTheDocument();
  });

  it("an unsuccessful save retries the identical draft and success restores a clean server state", () => {
    const view = show();
    fireEvent.click(screen.getByRole("checkbox", { name: "Payments: Email" }));
    const save = screen.getByRole("button", { name: "Save choices" });
    save.focus();
    expect(save).toHaveFocus();
    expect(save).toHaveAttribute("type", "submit");
    fireEvent.submit(screen.getByRole("form", { name: "Where your notifications go" }));
    expect(h.save.mutate).toHaveBeenCalledWith([{ category: "payments", channels: [], email_fallback: false,
      available_channels: ["email", "telegram"] }], expect.any(Object));
    h.save.error = new Error("Temporary failure");
    view.rerender(<MemoryRouter><MyNotificationSettings makerspaceId={4} member /></MemoryRouter>);
    expect(screen.getByRole("alert")).toHaveTextContent("Temporary failure");
    expect(screen.getByRole("checkbox", { name: "Payments: Email" })).not.toBeChecked();
    expect(screen.getByRole("button", { name: "Save choices" })).toBeEnabled();
    fireEvent.submit(screen.getByRole("form", { name: "Where your notifications go" }));
    expect(h.save.error).toEqual(new Error("Temporary failure"));
    const edited: Selection[] = [{ category: "payments", channels: [], email_fallback: false,
      available_channels: ["email", "telegram"] }];
    expect(h.save.mutate).toHaveBeenCalledTimes(2);
    expect(h.save.mutate).toHaveBeenNthCalledWith(1, edited, expect.any(Object));
    expect(h.save.mutate).toHaveBeenNthCalledWith(2, edited, expect.any(Object));
    const saved = { preferences: edited };
    act(() => { h.save.mutate.mock.calls[1][1].onSuccess(saved); });
    h.preferences.data = saved;
    h.save.error = null;
    h.save.isSuccess = true;
    view.rerender(<MemoryRouter><MyNotificationSettings makerspaceId={4} member /></MemoryRouter>);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Payments: Email" })).not.toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Payments: Telegram" })).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent("Saved.");
    expect(screen.getByRole("button", { name: "Save choices" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Discard" })).not.toBeInTheDocument();
  });

  it("Discard restores the server choices after a failed save", () => {
    const view = show();
    fireEvent.click(screen.getByRole("checkbox", { name: "Payments: Email" }));
    fireEvent.submit(screen.getByRole("form", { name: "Where your notifications go" }));
    h.save.error = new Error("Temporary failure");
    view.rerender(<MemoryRouter><MyNotificationSettings makerspaceId={4} member /></MemoryRouter>);
    expect(screen.getByRole("alert")).toHaveTextContent("Temporary failure");
    expect(screen.getByRole("checkbox", { name: "Payments: Email" })).not.toBeChecked();
    fireEvent.click(screen.getByRole("button", { name: "Discard" }));
    expect(screen.getByRole("checkbox", { name: "Payments: Email" })).toBeChecked();
    expect(screen.getByRole("button", { name: "Save choices" })).toBeDisabled();
  });
});

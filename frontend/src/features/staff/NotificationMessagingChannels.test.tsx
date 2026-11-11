import { afterEach, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { NotificationChannelPreferences } from "./NotificationChannelPreferences";
import type { NotificationRulesResponse } from "./notificationRuleTypes";
import { messagingFetch, renderMessaging } from "../../test/messagingFixtures";

afterEach(() => vi.unstubAllGlobals());
const rules: NotificationRulesResponse = {
  catalog: [], mutes: [], features: [{ key: "hardware_requests", label: "Hardware requests", events: ["accepted"] }],
  channels: [{ key: "sms", label: "SMS" }, { key: "whatsapp", label: "WhatsApp" }],
  preferences: [{ feature: "hardware_requests", channel: "sms", enabled: true, source: "override" },
    { feature: "hardware_requests", channel: "whatsapp", enabled: false, source: "default" }],
};

it("renders API channel labels, warns about missing enabled senders and updates the correct matrix cell", async () => {
  const writes: unknown[] = [];
  messagingFetch((url, options) => {
    if (options.method === "PATCH") { writes.push(JSON.parse(String(options.body))); return rules; }
    return url.pathname.endsWith("/channels") ? { count: 0, results: [], next: null, previous: null } : {};
  });
  renderMessaging(<NotificationChannelPreferences makerspaceId={11} rules={rules} />);
  expect(screen.getByRole("columnheader", { name: "SMS" })).toBeInTheDocument();
  expect(screen.getByRole("columnheader", { name: "WhatsApp" })).toBeInTheDocument();
  await screen.findByText("SMS needs sender setup or review under Communication channels.");
  fireEvent.click(screen.getByLabelText("Enable WhatsApp for Hardware requests"));
  await waitFor(() => expect(writes).toEqual([{ preferences: [{ feature: "hardware_requests", channel: "whatsapp", enabled: true }] }]));
});

it("does not request messaging settings when neither channel is present", async () => {
  const fetcher = messagingFetch(() => ({}));
  renderMessaging(<NotificationChannelPreferences makerspaceId={11} rules={{ ...rules, channels: [], preferences: [] }} />);
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));
  expect(String(fetcher.mock.calls[0][0])).toContain("/api-settings");
});

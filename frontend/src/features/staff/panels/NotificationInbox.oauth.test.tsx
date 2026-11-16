import { render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { NotificationInbox } from "./NotificationInbox";

vi.mock("../../notifications/PersonalInbox", () => ({ PersonalInbox: () => <div>Inbox</div> }));
vi.mock("../../notifications/MyNotificationSettings", () => ({ MyNotificationSettings: () => <div>OAuth return settings</div> }));
vi.mock("../BroadcastComposer", () => ({ BroadcastComposer: () => null }));
afterEach(() => window.history.replaceState(null, "", "/"));

it("opens staff channel settings for the exact registered redirect's state-only return", () => {
  window.history.replaceState(null, "", "/?code=provider-code&state=signed");
  const makerspace = { id: 8, name: "Lab", slug: "lab", public_code: "lab", telegram_group_chat_id: "",
    frontend_domain: null, hidden_from_central_directory: false, enabled_modules: ["notifications"], enabled_features: [] };
  render(<NotificationInbox makerspace={makerspace} />);
  expect(screen.getByText("OAuth return settings")).toBeInTheDocument();
});

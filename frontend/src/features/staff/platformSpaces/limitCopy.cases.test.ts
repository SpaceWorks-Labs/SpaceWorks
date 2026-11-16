import { describe, expect, it } from "vitest";
import { limitHint, limitLabel, limitSource, rateHint, rateLabel } from "./limitCopy";

const DEFAULT_HINT = "At the limit, new ones are refused until usage drops or the limit is raised.";

describe("limitLabel", () => {
  it.each([["products", "Products"], ["email_monthly", "Emails this month"], ["adapter_snapshots", "Camera snapshots requested this month"],
    ["anthias_players", "Anthias display players"], ["hardware_requests_monthly", "Hardware requests this month"]])("%s reads %s", (key, label) => expect(limitLabel(key)).toBe(label));
  it("prefers our translated name over the server label", () => expect(limitLabel("products", "Server products")).toBe("Products"));
  it("falls back to the server label for a key added later, capitalised", () => expect(limitLabel("brand_new", "extra thing")).toBe("Extra thing"));
  it("humanizes the key when the server label is missing or equals the key", () => {
    expect(limitLabel("brand_new_key")).toBe("Brand new key");
    expect(limitLabel("brand_new_key", "brand_new_key")).toBe("Brand new key");
  });
});

describe("limitHint", () => {
  it.each([
    ["members", "People with a membership here. At the limit, new joins wait until a place frees up."],
    ["staff", "People with a staff role. At the limit, no more staff can be added or invited."],
    ["storage", "Space used by photos, files and evidence. At the limit, new uploads are refused."],
    ["custom_domain", "Whether this space may use its own domain name."],
    ["email", "Emails sent by this space. At the limit, further emails wait until the count resets."],
    ["sms_monthly", "Text messages sent by this space. At the limit, further texts are not sent."],
    ["whatsapp", "WhatsApp messages sent by this space. At the limit, further messages are not sent."],
    ["slack", "Notifications sent through this channel per day. At the limit, more wait until tomorrow."],
    ["payments_monthly_amount", "New paid transactions this month on any rail (amounts per currency, in whole units). At the limit, new charges are refused; existing charges can always be paid."],
    ["platform_sms_monthly", "Counted only when the platform's credentials send for this space; its own credentials are never limited. At the limit, that channel skips and the inbox still delivers."],
    ["platform_payments_monthly_count", "Online payments through the platform's payment account (amounts per currency, in whole units). At the limit, pay at the desk or the space's own account still works."],
    ["shop_orders_monthly", "Counted this month. At the limit, new ones wait for next month."],
    ["shelf_checks_monthly", "Counted this month. At the limit, new ones wait for next month; existing ones carry on."],
    ["storage_evidence_bytes", "Space used by these files. At the limit, new uploads of this kind are refused."],
    ["anthias_players", "Anthias display players registered for the space screens. At the limit, no new player can be added."],
  ])("%s explains what happens at the limit", (key, hint) => expect(limitHint(key)).toBe(hint));
  it("gives a generic line for an unknown key", () => expect(limitHint("brand_new")).toBe(DEFAULT_HINT));
  it("gives every named limit its own specific line, never the generic one", () => {
    const named = ["members", "staff", "storage", "upload_bytes", "products", "assets", "machines", "events", "events_monthly", "bookings", "api_clients", "webhook_endpoints",
      "staff_cards_issued_monthly", "photo_cutout_jobs_monthly", "card_templates", "guest_passes", "data_exports", "print", "machine_service_open", "machine_service_submit",
      "custom_domain", "email", "sms", "whatsapp", "telegram", "bookings_monthly", "payments_monthly_count", "platform_email_monthly", "platform_wallet_monthly",
      "api_requests_per_minute", "storage_public_images_bytes", "event_registrations_monthly", "hardware_requests_monthly", "public_page_assets", "scheduled_reports",
      "adapter_media_bytes", "adapter_telemetry_points", "anthias_players"];
    for (const key of named) expect(limitHint(key), key).not.toBe(DEFAULT_HINT);
  });
});

describe("limitSource", () => {
  it.each([["own", "own space"], ["override", "set for this space"], ["plan", "from the plan"], ["default", "platform default"], ["unlimited", "no limit"]] as const)(
    "%s reads %s", (source, label) => expect(limitSource(source)).toBe(label));
});

describe("rates", () => {
  it("labels known scopes and humanizes unknown ones", () => {
    expect(rateLabel("login")).toBe("Sign-in attempts");
    expect(rateLabel("payment_claims")).toBe("\"I've paid\" claims");
    expect(rateLabel("brand_new_scope")).toBe("Brand new scope");
  });
  it("describes a known scope and appends the shared at-the-limit sentence", () => {
    expect(rateHint("login")).toBe("Password sign-in attempts per person and address. Above the rate, people see \"Too many requests\" and can try again shortly.");
  });
  it("uses a generic description for an unknown scope", () => expect(rateHint("brand_new_scope"))
    .toBe("Requests of this kind per person or address. Above the rate, people see \"Too many requests\" and can try again shortly."));
});

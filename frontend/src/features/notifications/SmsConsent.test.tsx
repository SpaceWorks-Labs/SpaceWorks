import { afterEach, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { SmsConsent } from "./SmsConsent";
import { MemberPhoneVerification } from "../members/MemberPhoneVerification";
import { memberMessaging, messagingFailure, messagingFetch, renderMessaging } from "../../test/messagingFixtures";
import { expectNoA11yViolations } from "../../test/axe";

afterEach(() => vi.unstubAllGlobals());

it("records explicit SMS consent without treating verified phone as WhatsApp proof", async () => {
  const writes: unknown[] = [];
  let current = structuredClone(memberMessaging);
  const fetcher = messagingFetch((url, options) => {
    expect(url.pathname).not.toContain("messaging-settings");
    if (options.method === "POST") {
      writes.push(JSON.parse(String(options.body)));
      current = { ...current, sms: { ...current.sms, consented: true } };
    }
    return current;
  });
  const { container } = renderMessaging(<SmsConsent makerspaceId={11} />);
  expect(await screen.findByLabelText("Allow SMS notifications")).not.toBeChecked();
  expect(screen.queryByLabelText("Allow WhatsApp notifications")).toBeNull();
  await expectNoA11yViolations(container);
  fireEvent.click(screen.getByLabelText("Allow SMS notifications"));
  await screen.findByText("SMS consent saved.");
  expect(writes).toEqual([{ makerspace: 11, channel: "sms", action: "opted_in" }]);
  expect(fetcher.mock.calls.some(([url]) => String(url).includes("/me/messaging/consent"))).toBe(true);
});

it("allows withdrawal after sender removal or phone expiry", async () => {
  let current = { ...memberMessaging, sms: { ...memberMessaging.sms, available: false, phone_verified: false, consented: true } };
  const writes: unknown[] = [];
  messagingFetch((_url, options) => {
    if (options.method === "POST") {
      writes.push(JSON.parse(String(options.body)));
      current = { ...current, sms: { ...current.sms, consented: false } };
    }
    return current;
  });
  renderMessaging(<SmsConsent makerspaceId={11} />);
  const checkbox = await screen.findByLabelText("Allow SMS notifications");
  expect(checkbox).toBeEnabled();
  fireEvent.click(checkbox);
  await waitFor(() => expect(writes).toEqual([{ makerspace: 11, channel: "sms", action: "opted_out" }]));
  await waitFor(() => expect(checkbox).toBeDisabled());
});

it("refuses stale phone verification without checking the consent box", async () => {
  messagingFetch((_url, options) => options.method === "POST"
    ? messagingFailure(409, { code: "phone_unverified", detail: "Verify your phone before opting in." }) : memberMessaging);
  renderMessaging(<SmsConsent makerspaceId={11} />);
  fireEvent.click(await screen.findByLabelText("Allow SMS notifications"));
  expect(await screen.findByRole("alert")).toHaveTextContent("Verify your phone");
  expect(screen.getByLabelText("Allow SMS notifications")).not.toBeChecked();
});

it("verifies a phone through the link flow and refreshes channels without subscribing", async () => {
  const writes: { path: string; body: unknown }[] = [];
  messagingFetch((url, options) => {
    writes.push({ path: url.pathname, body: JSON.parse(String(options.body)) });
    return url.pathname.endsWith("/start") ? { detail: "Verification code sent." } : { phone_e164: "+14155550101", verified: true };
  });
  const { client } = renderMessaging(<MemberPhoneVerification />);
  const invalidate = vi.spyOn(client, "invalidateQueries");
  fireEvent.change(screen.getByLabelText("Phone number (E.164)"), { target: { value: "+14155550101" } });
  fireEvent.click(screen.getByRole("button", { name: "Send verification code" }));
  fireEvent.change(await screen.findByLabelText("Verification code"), { target: { value: "012345" } });
  fireEvent.click(screen.getByRole("button", { name: "Verify phone" }));
  await screen.findByText("Phone verified. Choose your messaging consent next.");
  expect(writes).toEqual([
    { path: "/api/v1/auth/phone/link/start", body: { phone: "+14155550101" } },
    { path: "/api/v1/auth/phone/link/confirm", body: { phone: "+14155550101", code: "012345" } },
  ]);
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["notify-contract"] });
});

it("shows loading and a retryable read error without stale consent controls", async () => {
  let failed = true;
  messagingFetch(() => failed ? messagingFailure(503, { detail: "Consent temporarily unavailable" }) : memberMessaging);
  renderMessaging(<SmsConsent makerspaceId={11} />);
  expect(screen.getByRole("status")).toHaveTextContent("Loading SMS consent");
  await screen.findByText("Consent temporarily unavailable");
  expect(screen.queryByLabelText("Allow SMS notifications")).toBeNull();
  failed = false;
  fireEvent.click(screen.getByRole("button", { name: /Retry|Try again/i }));
  expect(await screen.findByLabelText("Allow SMS notifications")).toBeEnabled();
});


it("lets a verified staff account record its own sender-bound SMS consent", async () => {
  const writes: unknown[] = [];
  let current = structuredClone(memberMessaging);
  messagingFetch((_url, options) => {
    if (options.method === "POST") {
      writes.push(JSON.parse(String(options.body)));
      current = { ...current, sms: { ...current.sms, consented: true } };
    }
    return current;
  });
  renderMessaging(<SmsConsent makerspaceId={11} member={false} />);
  fireEvent.click(await screen.findByLabelText("Allow SMS notifications"));
  await screen.findByText("SMS consent saved.");
  expect(writes).toEqual([{ makerspace: 11, channel: "sms", action: "opted_in" }]);
});

it("keeps an unverified staff account out of the member phone-link flow", async () => {
  messagingFetch(() => ({ ...memberMessaging, sms: { ...memberMessaging.sms, phone_verified: false } }));
  renderMessaging(<SmsConsent makerspaceId={11} member={false} />);
  expect(await screen.findByLabelText("Allow SMS notifications")).toBeDisabled();
  expect(screen.queryByRole("button", { name: "Verify your phone first" })).toBeNull();
  expect(screen.getByText(/SMS requires a verified phone on this staff account/)).toBeVisible();
});

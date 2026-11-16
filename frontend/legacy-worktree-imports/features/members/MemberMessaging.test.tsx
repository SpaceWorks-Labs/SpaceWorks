// SKIPPED (not run, not type-checked): imported from a development worktree, kept for reference.
// Reason: Not in release 0.12.0: MemberMessaging component and lib messaging/messagingApi are not in release 0.12.0 (messaging UI lives under a different module).
// Excluded from vitest (vite.config.ts) and outside tsconfig "include"; rewrite against the release code before moving back under src/.
import { afterEach, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { MemberMessaging } from "./MemberMessaging";
import { MemberPhoneVerification } from "./MemberPhoneVerification";
import { memberMessaging, messagingFailure, messagingFetch, renderMessaging } from "../../test/messagingFixtures";
import { expectNoA11yViolations } from "../../test/axe";
import { memberMessagingKey } from "../messaging/messagingApi";

afterEach(() => vi.unstubAllGlobals());
const verifyPhoneHref = "/m/workshop/member/account-portal?section=phone";
const panel = <MemberMessaging makerspaceId={11} verifyPhoneHref={verifyPhoneHref} />;

it("shows availability, masked phones and STOP notice; posts per-channel consent", async () => {
  const writes: unknown[] = [];
  let current = structuredClone(memberMessaging);
  messagingFetch((_url, options) => {
    if (options.method === "POST") {
      const body = JSON.parse(String(options.body)); writes.push(body);
      current = { ...current, whatsapp: { ...current.whatsapp, consented: true, suppressed: false } };
    }
    return current;
  });
  const { client, container } = renderMessaging(panel);
  await screen.findByText("You replied STOP; turning this on again re-subscribes you.");
  expect(screen.getAllByText("Phone: +1••••0101")).toHaveLength(2);
  const invalidate = vi.spyOn(client, "invalidateQueries");
  await expectNoA11yViolations(container);
  fireEvent.click(screen.getByLabelText("Allow WhatsApp notifications"));
  await waitFor(() => expect(writes).toEqual([{ makerspace: 11, channel: "whatsapp", action: "opted_in" }]));
  await screen.findByText("Messaging consent saved.");
  expect(screen.queryByText(/You replied STOP/)).not.toBeInTheDocument();
  expect(invalidate).toHaveBeenCalledWith({ queryKey: memberMessagingKey(11), exact: true });
});

it("blocks unverified opt-in but allows opt-out even when unavailable and unverified", async () => {
  const writes: unknown[] = [];
  messagingFetch((_url, options) => {
    if (options.method === "POST") writes.push(JSON.parse(String(options.body)));
    return { sms: { ...memberMessaging.sms, phone_verified: false },
      whatsapp: { ...memberMessaging.whatsapp, consented: true, phone_verified: false, available: false } };
  });
  renderMessaging(panel);
  expect(await screen.findByLabelText("Allow SMS notifications")).toBeDisabled();
  expect(screen.getByLabelText("Allow WhatsApp notifications")).toBeEnabled();
  expect(screen.getAllByRole("link", { name: "Verify your phone first" })[0]).toHaveAttribute("href", verifyPhoneHref);
  fireEvent.click(screen.getByLabelText("Allow WhatsApp notifications"));
  await waitFor(() => expect(writes).toEqual([{ makerspace: 11, channel: "whatsapp", action: "opted_out" }]));
});

it.each(["phone_not_verified", "phone_unverified"])("shows a stale-verification 409 inline without granting consent (%s)", async code => {
  messagingFetch((_url, options) => options.method === "POST" ? messagingFailure(409, { code }) : memberMessaging);
  renderMessaging(panel);
  fireEvent.click(await screen.findByLabelText("Allow SMS notifications"));
  expect(await screen.findByRole("alert")).toHaveTextContent("Verify your phone first");
  expect(screen.getByLabelText("Allow SMS notifications")).not.toBeChecked();
});

it("isolates consent by makerspace without requesting notification preferences", async () => {
  const fetcher = messagingFetch(url => ({ sms: { ...memberMessaging.sms, consented: url.searchParams.get("makerspace") === "11" }, whatsapp: memberMessaging.whatsapp }));
  const { rerender, client } = renderMessaging(panel);
  expect(await screen.findByLabelText("Allow SMS notifications")).toBeChecked();
  rerender(<QueryClientProvider client={client}><MemoryRouter><MemberMessaging makerspaceId={12} verifyPhoneHref={verifyPhoneHref} /></MemoryRouter></QueryClientProvider>);
  await waitFor(() => expect(screen.getByLabelText("Allow SMS notifications")).not.toBeChecked());
  expect(client.getQueryData(memberMessagingKey(11))).toBeDefined();
  expect(client.getQueryData(memberMessagingKey(12))).toBeDefined();
  expect(fetcher.mock.calls.every(([url]) => String(url).includes("/me/messaging?makerspace="))).toBe(true);
});

it("reports unavailable channels and retries a failed read", async () => {
  let failed = true;
  messagingFetch(() => failed ? messagingFailure(503, { detail: "Temporarily unavailable" }) : { sms: { ...memberMessaging.sms, available: false }, whatsapp: memberMessaging.whatsapp });
  renderMessaging(panel);
  expect(await screen.findByRole("alert")).toHaveTextContent("Temporarily unavailable");
  failed = false; fireEvent.click(screen.getByRole("button", { name: "Retry messaging preferences" }));
  expect(await screen.findByLabelText("Allow SMS notifications")).toBeDisabled();
  expect(screen.getByText(/has no available SMS sender/)).toBeInTheDocument();
});

it("uses the existing phone-link endpoints and refreshes consent without opting in", async () => {
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
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["member", "messaging"] });
});

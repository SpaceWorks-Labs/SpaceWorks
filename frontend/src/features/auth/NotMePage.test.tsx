import { fireEvent, render as rtlRender, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
// Screens now read query-backed switches (help-centre bootstrap, #184 charge flags), so every render needs a client.
function render(ui: Parameters<typeof rtlRender>[0], options?: Parameters<typeof rtlRender>[1]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children?: Parameters<typeof rtlRender>[0] }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  return rtlRender(ui, { wrapper, ...options });
}
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "../../test/axe";
import { NotMePage } from "./NotMePage";

const fetchMock = vi.fn();
const json = (status: number, body: unknown) => Promise.resolve(new Response(JSON.stringify(body), {
  status, headers: { "Content-Type": "application/json" } }));
const RESULT = { signed_out: true, password_reset_requested: true,
  mfa_reset: { superadmin: true, space_managers_of: [{ name: "Fab Lab", slug: "fab" }] } };

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  window.history.replaceState(null, "", "/security/not-me#token=signed.alert.token");
});
afterEach(() => { vi.unstubAllGlobals(); document.head.querySelectorAll('meta[name="referrer"]').forEach(meta => meta.remove()); });

describe("NotMePage", () => {
  it("clears the fragment, sets no-referrer and sends nothing until the click", async () => {
    const { container } = render(<NotMePage />);
    expect(window.location.hash).toBe("");
    expect(window.location.pathname).toBe("/security/not-me");
    expect(document.head.querySelector('meta[name="referrer"]')).toHaveAttribute("content", "no-referrer");
    expect(screen.getByRole("heading", { level: 1, name: "Didn't do this?" })).toBeVisible();
    expect(screen.getByText("Your passkeys and authenticator app stay as they are.")).toBeInTheDocument();
    await new Promise(resolve => setTimeout(resolve, 20));
    expect(fetchMock).not.toHaveBeenCalled();
    await expectNoA11yViolations(container);
  });

  it("posts the token cookie-less on click and names who can reset two-step sign-in", async () => {
    fetchMock.mockReturnValue(json(200, RESULT));
    render(<NotMePage />);
    fireEvent.click(screen.getByRole("button", { name: "Secure my account" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Your account is secured" })).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/auth\/security-alerts\/not-me$/);
    expect(init).toMatchObject({ method: "POST", credentials: "omit", referrerPolicy: "no-referrer" });
    expect(JSON.parse(init.body)).toEqual({ token: "signed.alert.token" });
    expect(screen.getByText(/We emailed you a code to choose a new password/)).toBeInTheDocument();
    expect(screen.getByText(/ask the platform administrator or the Space Manager of Fab Lab/)).toBeInTheDocument();
  });

  it("shows plain copy for a used link and lets the person try again", async () => {
    fetchMock.mockReturnValue(json(400, { detail: "raw", code: "security_alert_used" }));
    render(<NotMePage />);
    fireEvent.click(screen.getByRole("button", { name: "Secure my account" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("This link was already used or has expired.");
    expect(screen.getByRole("alert")).not.toHaveTextContent("security_alert_used");
    await waitFor(() => expect(screen.getByRole("button", { name: "Secure my account" })).toBeEnabled());
  });

  it("explains an incomplete link and never posts", async () => {
    window.history.replaceState(null, "", "/security/not-me");
    vi.resetModules(); // a fresh page load: no token held from an earlier test
    const { NotMePage: FreshPage } = await import("./NotMePage");
    render(<FreshPage />);
    expect(screen.getByRole("heading", { level: 1, name: "This link is incomplete" })).toBeVisible();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

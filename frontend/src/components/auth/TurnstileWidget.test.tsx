import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiError } from "../../lib/api/errors";
import { TURNSTILE_SCRIPT_URL, type TurnstileApi } from "./turnstileScript";
import { tokenHeaders, useTurnstileGate } from "./useTurnstileGate";

const scripts = () => Array.from(document.head.querySelectorAll("script")).filter(script => script.src === TURNSTILE_SCRIPT_URL);
const refusal = apiError(400, { code: "captcha_required", turnstile_site_key: "server-key", turnstile_action: "login" });

let gate: ReturnType<typeof useTurnstileGate>;
function Harness({ configuredKey, onToken }: { configuredKey?: string; onToken: (token: string) => void }) {
  gate = useTurnstileGate(configuredKey, onToken);
  return <div>{gate.slot}</div>;
}

beforeEach(() => { scripts().forEach(script => script.remove()); delete window.turnstile; });
afterEach(() => { delete window.turnstile; });

describe("useTurnstileGate / TurnstileWidget", () => {
  it("says so when the script cannot load", async () => {
    // First in the file: the loader is a page-wide singleton, and a failed load lets the next one retry.
    render(<Harness configuredKey="config-key" onToken={vi.fn()} />);
    act(() => { gate.catchError(refusal); });
    await waitFor(() => expect(scripts()).toHaveLength(1));
    act(() => { scripts()[0].onerror?.(new Event("error")); });
    expect(await screen.findByText("The check couldn't load. Check your connection, then try again.")).toBeInTheDocument();
  });

  it("loads nothing when the deployment has no Turnstile key", () => {
    render(<Harness onToken={vi.fn()} />);
    let caught = true;
    act(() => { caught = gate.catchError(refusal); });
    expect(caught).toBe(false);
    expect(screen.queryByRole("group", { name: "Confirm you're a person" })).not.toBeInTheDocument();
    expect(scripts()).toHaveLength(0);
  });

  it("loads nothing for a refusal that is not a CAPTCHA", () => {
    render(<Harness configuredKey="config-key" onToken={vi.fn()} />);
    act(() => { expect(gate.catchError(apiError(429, { code: "ip_blocked" }))).toBe(false); });
    expect(scripts()).toHaveLength(0);
  });

  it("loads the script only after captcha_required and hands back the token", async () => {
    const onToken = vi.fn();
    render(<Harness configuredKey="config-key" onToken={onToken} />);
    expect(scripts()).toHaveLength(0);
    act(() => { expect(gate.catchError(refusal)).toBe(true); });
    expect(await screen.findByRole("group", { name: "Confirm you're a person" })).toBeInTheDocument();
    await waitFor(() => expect(scripts()).toHaveLength(1));
    const render_ = vi.fn<TurnstileApi["render"]>(() => "widget-1");
    window.turnstile = { render: render_, remove: vi.fn() };
    act(() => { scripts()[0].onload?.(new Event("load")); });
    await waitFor(() => expect(render_).toHaveBeenCalled());
    const [, options] = render_.mock.calls[0];
    expect(options).toMatchObject({ sitekey: "server-key", action: "login" });
    act(() => options.callback("turnstile-token"));
    expect(onToken).toHaveBeenCalledWith("turnstile-token");
    expect(tokenHeaders("turnstile-token")).toEqual({ "X-Turnstile-Token": "turnstile-token" });
    expect(tokenHeaders()).toEqual({});
  });

});

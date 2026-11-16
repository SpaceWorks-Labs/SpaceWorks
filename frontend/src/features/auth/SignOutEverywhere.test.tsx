import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { SignOutEverywhere } from "./SignOutEverywhere";
import { clearAccessToken, getAccessToken, refreshAccessToken, setAccessToken } from "../../lib/api/sessionTokens";
import { setRouteSessionContext, type SessionContext } from "../../lib/api/sessionContext";
import { queryClientForContext } from "../../lib/queryClient";
import { jobStore, trackJob } from "../../components/ui/jobStore";
import { toast, toastStore } from "../../components/ui/toastStore";
import { OFFLINE_CARD_PREFIX } from "../members/memberCard/offlineCard";
import { wipeOfflineScopes } from "../staff/eventCheckInOfflineStore";
import { listQueues, wipeQueue } from "../kiosk/offlineQueueStore";

vi.mock("../staff/eventCheckInOfflineStore", () => ({ wipeOfflineScopes: vi.fn(async () => undefined) }));
vi.mock("../kiosk/offlineQueueStore", () => ({ listQueues: vi.fn(async () => []), wipeQueue: vi.fn(async () => undefined) }));

const contexts: SessionContext[] = ["person", "platform"];
const token = (user: number, surface = "person") => `header.${btoa(JSON.stringify({ user_id: user, sid: "session-id", surface, email: "shared@example.test" }))}.signature`;
const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function Destination() {
  const location = useLocation();
  return <p>Sign in: {JSON.stringify({ path: location.pathname, search: location.search, hash: location.hash, state: location.state })}</p>;
}
function show(context: SessionContext) {
  setRouteSessionContext(context);
  const client = queryClientForContext(context);
  render(<MemoryRouter initialEntries={[{ pathname: "/security", search: "?next=private", hash: "#old", state: { next: "/private" } }]}>
    <QueryClientProvider client={client}><Routes>
      <Route path="/security" element={<SignOutEverywhere signInHref="/sign-in" />} />
      <Route path="/sign-in" element={<Destination />} />
    </Routes></QueryClientProvider>
  </MemoryRouter>);
  return client;
}

beforeEach(async () => {
  await Promise.all(contexts.map(clearAccessToken));
  contexts.forEach(context => queryClientForContext(context).clear());
  localStorage.clear();
  vi.clearAllMocks();
});
afterEach(() => { vi.unstubAllGlobals(); });

describe("account-wide sign-out", () => {
  it.each(contexts)("revokes %s and clears private data without clearing other accounts", async context => {
    const other = context === "person" ? "platform" : "person";
    setAccessToken(token(7, context === "platform" ? "platform" : context === "person" ? "delegated" : "staff_api"), context);
    setAccessToken(token(8), other);
    const foreignClient = queryClientForContext(other);
    foreignClient.setQueryData(["private"], "another principal");
    const client = show(context);
    client.setQueryData(["private"], "current principal");
    client.getMutationCache().build(client, { mutationKey: ["private-write"] });
    trackJob({ key: "export", label: "Private export", makerspaceId: 1, endpoint: "/private", status: "pending" });
    toast("Open private record", { action: { label: "Open", onClick: vi.fn() } });
    if (context === "person") localStorage.setItem(`${OFFLINE_CARD_PREFIX}/member`, "private card");
    vi.mocked(listQueues).mockResolvedValueOnce([
      { scope: "mine", lease: { actor_id: 7 } }, { scope: "theirs", lease: { actor_id: 8 } },
    ] as unknown as Awaited<ReturnType<typeof listQueues>>);
    const fetcher = vi.fn(async () => reply({ web_sessions: 2, devices: 1 }));
    vi.stubGlobal("fetch", fetcher);

    fireEvent.click(screen.getByRole("button", { name: "Sign out everywhere" }));

    await screen.findByText(/^Sign in:/);
    expect(fetcher).toHaveBeenCalledTimes(1);
    const [url, options] = fetcher.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toMatch(/\/auth\/logout-all$/);
    expect(options.method).toBe("POST");
    expect(options.credentials).toBe("include");
    expect(new Headers(options.headers).get("Authorization")).toContain("Bearer header.");
    expect(getAccessToken(context)).toBe("");
    expect(getAccessToken(other)).toBe(token(8));
    expect(client.getQueryCache().getAll()).toHaveLength(0);
    expect(client.getMutationCache().getAll()).toHaveLength(0);
    expect(foreignClient.getQueryData(["private"])).toBe("another principal");
    expect(jobStore.snapshot()).toEqual([]);
    expect(toastStore.snapshot()).toEqual([]);
    expect(wipeOfflineScopes).toHaveBeenCalledWith(`session:${context}:`);
    expect(wipeQueue).toHaveBeenCalledWith("mine");
    expect(wipeQueue).not.toHaveBeenCalledWith("theirs");
    if (context === "person") expect(localStorage.getItem(`${OFFLINE_CARD_PREFIX}/member`)).toBeNull();
    expect(screen.getByText(/^Sign in:/)).toHaveTextContent('"search":"","hash":"","state":null');
  });

  it("fences a refresh already in flight when logout succeeds", async () => {
    setAccessToken(token(7), "person");
    let complete!: (response: Response) => void;
    vi.stubGlobal("fetch", vi.fn((url: string) => url.endsWith("/refresh")
      ? new Promise<Response>(resolve => { complete = resolve; })
      : Promise.resolve(reply({ web_sessions: 1, devices: 0 }))));
    const refreshing = refreshAccessToken("person");
    show("person");
    fireEvent.click(screen.getByRole("button", { name: "Sign out everywhere" }));
    await screen.findByText(/^Sign in:/);
    complete(reply({ access: token(7) }));
    expect(await refreshing).toBe(false);
    expect(getAccessToken("person")).toBe("");
  });

  it.each(["network", "refused"])("retains the session and offers retry after %s failure", async failure => {
    setAccessToken(token(7), "person");
    const client = show("person");
    client.setQueryData(["private"], "kept");
    vi.stubGlobal("fetch", vi.fn(async () => {
      if (failure === "network") throw new Error("Network unavailable");
      return reply({ detail: "Unable to revoke sessions" }, 503);
    }));
    fireEvent.click(screen.getByRole("button", { name: "Sign out everywhere" }));
    await screen.findByRole("alert");
    expect(getAccessToken("person")).toBe(token(7));
    expect(client.getQueryData(["private"])).toBe("kept");
    expect(screen.getByRole("button", { name: "Sign out everywhere" })).toBeEnabled();
    expect(screen.queryByText(/^Sign in:/)).not.toBeInTheDocument();
  });

  it("disables duplicate clicks until the server confirms revocation", async () => {
    setAccessToken(token(7), "person");
    let complete!: (response: Response) => void;
    const fetcher = vi.fn(() => new Promise<Response>(resolve => { complete = resolve; }));
    vi.stubGlobal("fetch", fetcher);
    show("person");
    fireEvent.click(screen.getByRole("button", { name: "Sign out everywhere" }));
    expect(screen.getByRole("button", { name: "Signing out…" })).toBeDisabled();
    expect(getAccessToken("person")).toBe(token(7));
    await waitFor(() => expect(fetcher).toHaveBeenCalled());
    complete(reply({ web_sessions: 1, devices: 0 }));
    await waitFor(() => expect(getAccessToken("person")).toBe(""));
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("clears a locally supplied query provider too", async () => {
    setRouteSessionContext("person"); setAccessToken(token(7), "person");
    vi.stubGlobal("fetch", vi.fn(async () => reply({ web_sessions: 1, devices: 0 })));
    const client = new QueryClient(); client.setQueryData(["private"], "embedded data");
    render(<MemoryRouter><QueryClientProvider client={client}><SignOutEverywhere signInHref="/sign-in" /></QueryClientProvider></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", { name: "Sign out everywhere" }));
    await waitFor(() => expect(client.getQueryCache().getAll()).toHaveLength(0));
  });
});

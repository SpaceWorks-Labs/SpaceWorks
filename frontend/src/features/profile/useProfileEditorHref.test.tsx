import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { cacheTenantPublishableKey, publicV1Request, setRuntimePublishableKey } from "../../lib/api";
import { memberProfileKey } from "./edit/profileEditApi";
import { useProfileEditorHref } from "./useProfileEditorHref";

const json = (body: unknown) => new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" } });

function Editor() {
  const editor = useProfileEditorHref("maker.one", true, false);
  return <output>{editor.href}</output>;
}

afterEach(() => vi.unstubAllGlobals());

it("keeps public requests on their tenant when an uncached nonmatch precedes a cached matching editor", async () => {
  setRuntimePublishableKey("");
  cacheTenantPublishableKey("target", "pk-target");
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(["member", "target", "bootstrap"], {
    makerspace: { id: 3, slug: "target" }, modules: ["membership"], public_api: { publishable_key: "pk-target" },
  });
  client.setQueryData(memberProfileKey(3), { handle: "maker.one" });
  const request = vi.fn(async (url: string, _options?: RequestInit) => {
    if (url.endsWith("/memberships/me")) return json({ memberships: [
      { makerspace: { slug: "other" }, membership_status: "active" },
      { makerspace: { slug: "target" }, membership_status: "active" },
    ] });
    if (url.endsWith("/bootstrap?slug=other")) return json({ makerspace: { id: 4, slug: "other" },
      modules: ["membership"], public_api: { publishable_key: "pk-other" } });
    if (url.endsWith("/member/makerspaces/4/profile")) return json({ handle: null });
    if (url.endsWith("/public/profiles/maker.one/projects?page=1")) return json({ results: [] });
    throw new Error(`Unexpected ${url}`);
  });
  vi.stubGlobal("fetch", request);
  render(<QueryClientProvider client={client}><Editor /></QueryClientProvider>);
  expect(await screen.findByText("/m/target/member/account-portal?section=profile")).toBeVisible();
  await publicV1Request("/public/profiles/maker.one/projects?page=1");
  expect(request).toHaveBeenCalledTimes(4);
  expect(new Headers(request.mock.calls[2][1]?.headers).get("X-Publishable-Key")).toBe("pk-other");
  expect(new Headers(request.mock.calls[3][1]?.headers).get("X-Publishable-Key")).toBe("pk-target");
});

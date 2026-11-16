import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";

const { bootstrapTenant, memberRequest } = vi.hoisted(() => ({ bootstrapTenant: vi.fn(), memberRequest: vi.fn() }));
vi.mock("../../lib/api", async () => ({
  ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"),
  bootstrapTenant, memberRequest, refreshAccessToken: vi.fn().mockResolvedValue(undefined),
}));
import { MemberArea } from "./MemberArea";

afterEach(() => { vi.restoreAllMocks(); document.documentElement.className = ""; });

it.each(["light", "dark", "invalid"])("renders member support contacts and scoped tokens for %s palettes", async (mode) => {
  document.documentElement.classList.toggle("dark", mode === "dark");
  const primary = mode === "dark" ? "#004400" : mode === "invalid" ? "red" : "#fff";
  bootstrapTenant.mockResolvedValue({
    makerspace: { id: 7, slug: "brand-space", name: "Brand Space", membership_policy: "invite_only" },
    modules: [], theme: { primary_color: primary, accent_color: "#000" },
    branding: { support_email: "help@example.com", support_url: "https://example.com/help" },
  });
  memberRequest.mockImplementation(async (path: string) => {
    if (path === "/memberships/me") return { memberships: [], requests: [] };
    if (path === "/memberships/invitations") return { invitations: [] };
    if (path.endsWith("payments")) return [];
    return {};
  });
  const tokens: Record<string, string> = {
    "on-brand": "255 244 232", brand: "0 110 99",
    bg: "255 244 232", surface: "246 236 224", panel: "255 255 255", hover: "239 230 219",
  };
  if (mode === "dark") Object.assign(tokens, { bg: "20 44 42", surface: "27 50 48", panel: "34 56 53", hover: "46 66 63" });
  vi.spyOn(window, "getComputedStyle").mockReturnValue({
    getPropertyValue: (name: string) => tokens[name.replace("--color-", "")] ?? "",
  } as CSSStyleDeclaration);
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter><MemberArea /></MemoryRouter>
  </QueryClientProvider>);
  expect(await screen.findByRole("link", { name: "help@example.com" })).toHaveAttribute("href", "mailto:help@example.com");
  expect(screen.getByRole("link", { name: "Contact support" })).toHaveAttribute("href", "https://example.com/help");
  const main = screen.getByRole("main");
  const style = (main.closest("[data-app-shell]")!.parentElement as HTMLElement).style;
  if (mode === "invalid") {
    expect(style.length).toBe(0);
  } else {
    expect(style.getPropertyValue("--color-brand")).toBe(mode === "dark" ? "0 68 0" : "255 255 255");
    expect(style.getPropertyValue("--color-on-brand")).toBe(mode === "dark" ? "255 244 232" : "20 44 42");
    expect(style.getPropertyValue("--color-brand-hover")).toBe(mode === "dark" ? "26 86 23" : "232 234 234");
    expect(style.getPropertyValue("--color-brand-active")).toBe(mode === "dark" ? "51 103 46" : "208 213 212");
    expect(style.getPropertyValue("--color-brand-boundary")).toBe(style.getPropertyValue("--color-brand-ink"));
  }
  expect(document.documentElement.style.getPropertyValue("--color-brand")).toBe("");
});

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { helpArticle } from "./helpContent";
import { PageHelp } from "./PageHelp";

const bootstrap = vi.hoisted(() => ({ features: ["platform.help_centre"] as string[] }));
vi.mock("../inventory/usePublicInventory", () => ({
  useTenantBootstrap: (slug: string) => ({ data: slug ? { makerspace: { slug }, features: bootstrap.features } : undefined }),
}));

function at(path: string, pattern: string, node = <PageHelp article="member/calendar-links" topic="calendar links" />) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}>
    <Routes><Route path={pattern} element={node} /></Routes></MemoryRouter></QueryClientProvider>);
}

const SOURCES = import.meta.glob(["../**/*.tsx", "!../**/*.test.tsx"], { query: "?raw", import: "default", eager: true }) as Record<string, string>;
const source = (suffix: string) => Object.entries(SOURCES).find(([path]) => path.endsWith(suffix))?.[1] ?? "";

describe("Help links on member and public pages", () => {
  it("opens the space's guide from a /m/<slug> page, in a new tab, naming the topic", () => {
    bootstrap.features = ["platform.help_centre"];
    at("/m/tinkerspace/member/cards", "/m/:slug/member/cards");
    const link = screen.getByRole("link", { name: "Help with calendar links (opens in a new tab)" });
    expect(link).toHaveAttribute("href", "/m/tinkerspace/help/member/calendar-links");
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("opens the central guide when the page has no space", () => {
    at("/security/not-me", "/security/not-me");
    expect(screen.getByRole("link")).toHaveAttribute("href", "/help/member/calendar-links");
  });

  it("shows nothing when the space turned its help centre off", () => {
    bootstrap.features = [];
    at("/m/tinkerspace/member/cards", "/m/:slug/member/cards");
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("mounts the pages the help-centre lane listed, each on an article that exists", () => {
    const mounts = {
      "/members/wallet/WalletPage.tsx": "member/member-card",
      "/members/calendarFeeds/MemberCalendarLinks.tsx": "member/calendar-links",
      "/events/participation/ApplicationReviewsPage.tsx": "member/event-participation",
      "/auth/NotMePage.tsx": "member/security-alerts",
    };
    for (const [file, article] of Object.entries(mounts)) {
      expect(source(file), file).toContain(`<PageHelp article="${article}"`);
      expect(helpArticle(article), article).toBeDefined();
    }
  });
});

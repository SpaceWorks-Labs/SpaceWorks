import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { expectNoA11yViolations } from "../../test/axe";
import { DeskCollectPanel } from "../staff/eventTicketing/DeskCollectPanel";
import { PriceDropDialog } from "../staff/priceDrop/PriceDropDialog";
import { helpArticle } from "./helpContent";
import { ScreenHelp } from "./HelpLink";
import { StaffHelpContext, type StaffHelpPlace } from "./staffHelpContext";
import { STAFF_SUBSCREEN_HELP } from "./staffScreenHelp";

const on = { slug: "tinkerspace", enabled_features: ["platform.help_centre"] };
const off = { slug: "tinkerspace", enabled_features: [] };

function inStaff(node: ReactNode, place: StaffHelpPlace = { makerspace: on }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><StaffHelpContext.Provider value={place}>{node}</StaffHelpContext.Provider></QueryClientProvider>);
}

// Every source file, read as text, to prove each map line has a mount somewhere.
const SOURCES = import.meta.glob(["../**/*.tsx", "!../**/*.test.tsx"], { query: "?raw", import: "default", eager: true }) as Record<string, string>;
const mounted = (key: string) => {
  const prefix = key.slice(0, key.indexOf("."));
  return Object.values(SOURCES).some(source => source.includes(`screen="${key}"`) || source.includes(`screen={\`${prefix}.\${`));
};

describe("Help links on staff sub-screens", () => {
  it("opens the sub-screen's article in a new tab and names its topic", async () => {
    const { container } = inStaff(<ScreenHelp screen="cards.programmes" />);
    const link = screen.getByRole("link", { name: "Help with ID programmes (opens in a new tab)" });
    expect(link).toHaveAttribute("href", "/m/tinkerspace/help/space-manager/id-programmes");
    expect(link).toHaveAttribute("target", "_blank");
    // Visibly distinct from the console's page-level "Help" link above it.
    expect(link).toHaveTextContent("Help with ID programmes");
    await expectNoA11yViolations(container);
  });

  it("keeps the single-space origin and the superadmin's platform session", () => {
    inStaff(<ScreenHelp screen="shop.pos" />, { makerspace: on, singleTenant: true, platform: true });
    expect(screen.getByRole("link")).toHaveAttribute("href", "/help/shop-manager/front-desk-sales?context=platform");
  });

  it("shows nothing outside the staff workspace, when the help centre is off, or for an unmapped sub-screen", () => {
    const { container, unmount } = render(<ScreenHelp screen="cards.programmes" />);
    expect(container).toBeEmptyDOMElement();
    unmount();
    inStaff(<><ScreenHelp screen="events.crew" /><ScreenHelp screen="shop.settings" /></>, { makerspace: off });
    expect(screen.queryByRole("link")).toBeNull();
    inStaff(<ScreenHelp screen="shop.settings" />);
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("resolves every sub-screen line to an article and mounts every line somewhere", () => {
    for (const [key, entry] of Object.entries(STAFF_SUBSCREEN_HELP)) {
      expect(helpArticle(entry.article), `${key} -> ${entry.article}`).toBeDefined();
      expect(entry.topic, key).not.toBe("");
      expect(mounted(key), `${key} has no <ScreenHelp> mount`).toBe(true);
    }
  });

  it("covers the sub-screens the help-centre lane listed", () => {
    for (const key of ["cards.programmes", "members.import", "events.certificates", "events.applications", "events.crew",
      "events.checkin-lists", "events.orders", "events.desk-collect", "events.series-passes", "events.venue-fees",
      "events.judging-extras", "finance.donations", "finance.sponsors", "finance.price-drop", "pages.sponsors",
      "shop.orders", "shop.pos", "shop.cash", "shop.catalogue", "shop.stock", "shop.reports"]) {
      expect(STAFF_SUBSCREEN_HELP[key], key).toBeDefined();
    }
  });

  it("puts the account security page's Help link on the two-step article", () => {
    const source = Object.entries(SOURCES).find(([path]) => path.endsWith("/auth/MfaAccountPage.tsx"))?.[1] ?? "";
    expect(source).toContain('<HelpLink article="member/two-step-sign-in"');
  });
});

describe("Help links mounted in real staff screens", () => {
  it("the price-drop dialog links the price-drop refunds article", () => {
    inStaff(<PriceDropDialog report={{ count: 1, truncated: false, items: [], totals: [{ currency: "INR", difference: "50.00" }] }}
      onConfirm={() => {}} onClose={() => {}} />);
    expect(screen.getByRole("link", { name: /Help with lowering a price/ })).toHaveAttribute("href", "/m/tinkerspace/help/finance/price-drop-refunds");
  });

  it("the desk payment panel links the paid-ticketing article", () => {
    inStaff(<DeskCollectPanel registrationId={7} />);
    expect(screen.getByRole("link", { name: /Help with desk payments/ })).toHaveAttribute("href", "/m/tinkerspace/help/event-manager/paid-ticketing");
  });

  it("the same dialog outside the staff workspace shows no Help link", () => {
    render(<PriceDropDialog report={{ count: 0, truncated: false, items: [], totals: [] }} onConfirm={() => {}} onClose={() => {}} />);
    expect(screen.queryByRole("link")).toBeNull();
  });
});

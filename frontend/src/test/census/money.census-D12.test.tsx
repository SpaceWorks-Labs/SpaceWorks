/// <reference types="node" />
// CX9 C5 cell 242 (frontend_shell): every screen that renders money, per charge domain and switch.
// Population (drift-guarded): every non-test source file that decides money UI through
// `useChargesOn` / `chargesOn` or renders `<PricePreview>`, with the domain(s) it passes. Behaviour:
// `chargesOn` hides money only on an explicit false (fails open while loading); `PricePreview` for every
// domain x charges on/off: off -> no quote request and nothing rendered (a free domain shows no money),
// on + priced -> the amount with its currency, on + nothing owed -> "Free" and no total.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, relative, resolve } from "node:path";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { tenantPublicRequest } from "../../lib/api";
import { chargesOn, type ChargeDomain } from "../../lib/charges";
import { PricePreview } from "../../features/payments/PricePreview";
import type { PricingPublicQuote } from "../../features/payments/usePriceQuote";

const DOMAINS: ChargeDomain[] = ["loans", "machines", "bookings", "events", "membership", "shop", "donations"];
const tracked: { value: Partial<Record<ChargeDomain, boolean>> } = { value: {} };
vi.mock("../../lib/api", () => ({ tenantPublicRequest: vi.fn() }));
vi.mock("../../lib/tenant", async (importOriginal) => ({ ...await importOriginal<typeof import("../../lib/tenant")>(),
  useTenant: () => ({ mode: "single", bootstrap: { charges_tracked: tracked.value } }) }));

// file (relative to src) -> charge domains its money UI is decided by. Reviewed; a new consumer fails here.
const CONSUMERS: Record<string, string[]> = {
  "features/bookings/PublicBookingForm.tsx": ["bookings"],
  "features/bookings/PublicBookingResourcePage.tsx": ["bookings"],
  "features/donations/DonatePage.tsx": ["donations"],
  "features/events/MemberEventTicketPage.tsx": ["events"],
  "features/events/hackathonAdmission/AdmissionFields.tsx": ["events"],
  "features/events/hackathonAdmission/ApplicationStatus.tsx": ["events"],
  "features/events/hackathonSubmissions/ProgrammeCharges.tsx": ["events"],
  "features/events/ticketing/MemberSeriesPassPage.tsx": ["events"],
  "features/events/ticketing/TicketManageActions.tsx": ["events"],
  "features/inventory/EventRegistrationEntry.tsx": ["events"],
  "features/inventory/EventRegistrationForm.tsx": ["events"],
  "features/inventory/MachineIntakeForm.tsx": ["machines"],
  "features/inventory/PublicEventDetailPage.tsx": ["events", "shop"],
  "features/inventory/PublicEventsPage.tsx": ["events"],
  "features/inventory/PublicRequestPanel.tsx": ["loans"],
  "features/machine-jobs/JobRequestPage.tsx": ["machines"],
  "features/members/MemberArea.tsx": ["membership"],
  "features/printing/PublicPrintRequestPage.tsx": ["machines"],
  "features/public/FeaturedActivities.tsx": ["events"],
  "features/publicPages/ProjectedEventCollection.tsx": ["events"],
  "features/publicPages/PublicPlanCards.tsx": ["membership"],
  "features/publicPages/PublicShopCards.tsx": ["shop"],
};

function srcRoot() {
  for (let directory = resolve(process.cwd()); ; directory = dirname(directory)) {
    for (const candidate of [resolve(directory, "src"), resolve(directory, "frontend/src")]) {
      if (existsSync(resolve(candidate, "lib/charges.ts"))) return candidate;
    }
    if (dirname(directory) === directory) throw new Error("money census cannot locate frontend/src");
  }
}

function files(directory: string): string[] {
  return readdirSync(directory).flatMap((name) => {
    const path = resolve(directory, name);
    if (statSync(path).isDirectory()) return name === "generated" || name === "test" ? [] : files(path);
    return /\.tsx?$/.test(name) && !/\.test\.tsx?$/.test(name) ? [path] : [];
  });
}

function liveConsumers() {
  const src = srcRoot();
  const own = new Set(["lib/charges.ts", "features/payments/PricePreview.tsx"]);
  const found: Record<string, string[]> = {};
  for (const path of files(src)) {
    const file = relative(src, path).split("\\").join("/");
    const text = readFileSync(path, "utf8");
    if (own.has(file) || !/useChargesOn\(|chargesOn\(|<PricePreview\b/.test(text)) continue;
    const domains = new Set<string>();
    for (const match of text.matchAll(/useChargesOn\(\s*["'](\w+)["']|chargesOn\([^,()]+,\s*["'](\w+)["']\)/g)) domains.add(match[1] ?? match[2]);
    for (const match of text.matchAll(/<PricePreview[^>]*?domain:\s*["'](\w+)["']/gs)) domains.add(match[1]);
    found[file] = [...domains].sort();
  }
  return found;
}

const quote = (total: string): PricingPublicQuote => ({
  quote: { domain: "loans", currency: "eur", mode: "paid", lines: total === "0.00" ? [] : [{ component: "fee", label: "Fee", subject_type: "x",
    quantity: "1.0000", unit_amount: total, gross: total, discount: "0.00", net: total, source: "default", cap_applied: false,
    target: null, detail: {} }], subtotal: total, discount_total: "0.00", total, discount: null, waiver: null, notes: [], digest: "d" },
  digest: "d", tax: { net: total, tax: "0.00", gross: total, inclusive: false, mode: "none" }, members_total: null,
  member_price_applied: false, deposit: null, policy: null, refund_summary: null,
} as unknown as PricingPublicQuote);

// The smallest request each domain's quote accepts (usePriceQuote.quoteReady).
const READY: Record<ChargeDomain, object> = {
  loans: { domain: "loans", items: [{ product_id: 1, quantity: 1 }] },
  bookings: { domain: "bookings", space_id: 1, starts_at: "2030-01-01T10:00:00Z", ends_at: "2030-01-01T11:00:00Z" },
  machines: { domain: "machines", machine_id: 1 }, events: { domain: "events", event_id: 1 },
  membership: { domain: "membership", joining: true }, shop: { domain: "shop" }, donations: { domain: "donations" },
};

function show(node: ReactNode) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{node}</QueryClientProvider>);
}

describe("money census (D12, C5 frontend_shell)", () => {
  beforeEach(() => { vi.mocked(tenantPublicRequest).mockReset(); tracked.value = {}; });

  it("pins every money consumer and the domain it decides money by", () => {
    const live = liveConsumers();
    expect(live).toEqual(CONSUMERS);
    for (const domains of Object.values(live)) for (const domain of domains) expect(DOMAINS).toContain(domain);
  });

  it.each(DOMAINS)("chargesOn(%s) hides money only on an explicit false", (domain) => {
    expect(chargesOn({ charges_tracked: { [domain]: false } } as never, domain)).toBe(false);
    expect(chargesOn({ charges_tracked: { [domain]: true } } as never, domain)).toBe(true);
    expect(chargesOn({ charges_tracked: {} } as never, domain)).toBe(true);
    expect(chargesOn(undefined, domain)).toBe(true);
  });

  it.each(DOMAINS)("a free %s domain neither asks for a quote nor renders money", async (domain) => {
    tracked.value = { [domain]: false };
    const { container } = show(<PricePreview makerspaceSlug="lab" request={READY[domain] as never} />);
    await new Promise((settle) => setTimeout(settle, 500));
    expect(tenantPublicRequest).not.toHaveBeenCalled();
    expect(container).toBeEmptyDOMElement();
  });

  it.each(DOMAINS)("a charging %s domain shows the quoted amount with its currency", async (domain) => {
    tracked.value = { [domain]: true };
    vi.mocked(tenantPublicRequest).mockResolvedValue(quote("12.50"));
    show(<PricePreview makerspaceSlug="lab" request={READY[domain] as never} />);
    expect(await screen.findByText("Total")).toBeVisible();
    expect(screen.getByText("Total").parentElement).toHaveTextContent("€12.50");
    await waitFor(() => expect(tenantPublicRequest).toHaveBeenCalledTimes(1));
  });

  it.each(DOMAINS)("a charging %s domain that owes nothing says Free and shows no total", async (domain) => {
    tracked.value = { [domain]: true };
    vi.mocked(tenantPublicRequest).mockResolvedValue(quote("0.00"));
    show(<PricePreview makerspaceSlug="lab" request={READY[domain] as never} />);
    expect(await screen.findByText("Free")).toBeVisible();
    expect(screen.queryByText("Total")).toBeNull();
  });
});

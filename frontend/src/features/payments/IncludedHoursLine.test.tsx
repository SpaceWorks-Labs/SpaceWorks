import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import { StaffPriceConfirmation } from "../staff/StaffPriceConfirmation";
import { IncludedHoursLine, type IncludedHoursSummary } from "./IncludedHoursLine";
import { QuoteLines } from "./PricePreviewDetails";
import type { PricingPublicQuote } from "./usePriceQuote";

const info: IncludedHoursSummary = { kind: "booking", term_id: 3, plan_name: "Studio plan", term_ends_at: "2026-12-01T00:00:00Z",
  allowance_minutes: 600, applied_minutes: 90, applied_hours: "1.50", remaining_minutes: 360, remaining_hours: "6.00" };

it("says how many hours this booking uses and how many are left", () => {
  render(<IncludedHoursLine info={info} />);
  expect(screen.getByText("1.5 h included")).toBeInTheDocument();
  expect(screen.getByText("6 h left this term")).toBeInTheDocument();
});

it("renders nothing without included hours", () => {
  const { container } = render(<IncludedHoursLine info={null} />);
  expect(container).toBeEmptyDOMElement();
});

it("adds the line to the member and public quote", () => {
  const data = { quote: { currency: "usd", lines: [], discount_total: "0", waiver: null, discount: null, included_hours: info } } as unknown as PricingPublicQuote;
  render(<QuoteLines data={data} />);
  expect(screen.getByText("1.5 h included")).toBeInTheDocument();
});

it("adds the line to the staff price confirmation, also when charges are off", () => {
  render(<StaffPriceConfirmation approval={false} confirmation={{ charges: "off", quote: null, price_confirmation: "d", included_hours: { ...info, applied_minutes: 0, applied_hours: "0.00" } }} />);
  expect(screen.getByText("No included hours used")).toBeInTheDocument();
  expect(screen.getByText("6 h left this term")).toBeInTheDocument();
});

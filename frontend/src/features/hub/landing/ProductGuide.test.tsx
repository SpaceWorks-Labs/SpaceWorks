import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { findDoc } from "../../docs/docsIndex";
import { ProductGuide } from "./ProductGuide";

describe("product catalogue shared by landing and Features", () => {
  it("keeps the ledger, free shop exception, required dependencies and TV pairing instructions", () => {
    render(<MemoryRouter><ProductGuide /></MemoryRouter>);
    expect(screen.getByText(/^Membership and mobile apps require member accounts\./)).toHaveTextContent(
      "Event reimbursements require events. These are installation requirements.");
    expect(screen.getByText(/^Every module can run free\./)).toHaveTextContent(
      "Shop catalogue and stock work free; selling requires charges.shop.");
    expect(screen.getByText(/^The payments module adds Stripe/)).toHaveTextContent(
      "Turning off charging never erases a debt, receipt or refund case.");
    expect(screen.getByText(/^Open \/display on the TV/)).toHaveTextContent(
      "enter its six-character pairing code in the console within 30 minutes.");
    expect(screen.getByText(/^Existing records remain available\./)).toHaveTextContent(
      "the operator must raise exhausted allowances before handover can finish.");
  });

  it("links only to guides published in the same-domain in-app docs", () => {
    render(<MemoryRouter><ProductGuide /></MemoryRouter>);
    const links = screen.getAllByRole("link");
    expect(links.map(link => link.getAttribute("href"))).toEqual([
      "/docs/api-guide", "/docs/features", "/docs/how-to/display-screens", "/docs/how-to/anthias",
    ]);
    for (const link of links) expect(findDoc(link.getAttribute("href")!.slice("/docs/".length))).toBeDefined();
  });
});

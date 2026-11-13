import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AmountPicker, CampaignHero, CampaignPicker } from "./AmountPicker";
import type { Campaign, DonationPage } from "./donationsApi";

// MOD-3 flow audit (donations screen states): empty suggestions, pressed state, goal boundaries, supporters plural, RTL.
const page = { currency: "inr", minimum_amount: "10.00", suggested_amounts: ["500", "1000"] } as unknown as DonationPage;
const campaign = (over: Partial<Campaign> = {}): Campaign => ({ id: 4, kind: "campaign", name: "New laser", slug: "laser", description: "",
  goal_amount: "10000.00", raised_amount: "2500.00", currency: "inr", starts_at: null, ends_at: null, ...over } as Campaign);

describe("AmountPicker", () => {
  it("marks the chosen suggestion pressed and sends the raw amount string", () => {
    const onAmount = vi.fn();
    render(<AmountPicker page={page} amount="500" onAmount={onAmount} />);
    expect(screen.getByRole("button", { name: "₹500.00" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "₹1,000.00" })).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(screen.getByRole("button", { name: "₹1,000.00" }));
    expect(onAmount).toHaveBeenCalledWith("1000");
  });

  it("has no suggestion group when the space offers none, and states the minimum gift", () => {
    render(<AmountPicker page={{ ...page, suggested_amounts: [] }} amount="" onAmount={() => {}} />);
    expect(screen.queryByRole("group", { name: "Suggested amounts" })).not.toBeInTheDocument();
    expect(screen.getByText(/smallest gift here is/)).toBeInTheDocument();
    const input = screen.getByRole("textbox");
    expect(input).toBeRequired();
    expect(input).toHaveAttribute("pattern", "[0-9]+(\\.[0-9]{1,3})?"); // up to three decimals, never a fourth
  });
});

describe("CampaignHero", () => {
  it("caps the progress bar's share at 100 percent when the goal is exceeded", () => {
    render(<CampaignHero campaign={campaign({ raised_amount: "15000.00" })} />);
    expect(screen.getByRole("progressbar", { name: /150 percent of the goal raised/ })).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "100");
  });

  it("shows only the raised-so-far line when there is no goal, and singular/plural supporters", () => {
    const { rerender } = render(<CampaignHero campaign={campaign({ goal_amount: null, supporter_count: 1 } as Partial<Campaign>)} />);
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    expect(screen.getByText(/raised so far/)).toBeInTheDocument();
    expect(screen.getByText("1 supporter so far.")).toBeInTheDocument();
    rerender(<CampaignHero campaign={campaign({ goal_amount: null, supporter_count: 3, supporters: ["مريم", "Asha 🎉"] } as Partial<Campaign>)} />);
    expect(screen.getByText("3 supporters so far.")).toBeInTheDocument();
    expect(screen.getByText(/مريم, Asha 🎉/)).toBeInTheDocument();
  });
});

describe("CampaignPicker", () => {
  it("renders nothing without campaigns, offers general giving, and reports the picked campaign", () => {
    const { container, rerender } = render(<CampaignPicker campaigns={[]} value={null} onChange={() => {}} />);
    expect(container).toBeEmptyDOMElement();
    const onChange = vi.fn();
    rerender(<CampaignPicker campaigns={[campaign()]} value={null} onChange={onChange} pageHref={(slug) => `/c/${slug}`} />);
    expect(screen.getByRole("radio", { name: /Wherever it helps most/ })).toBeChecked();
    fireEvent.click(screen.getByRole("radio", { name: /New laser/ }));
    expect(onChange).toHaveBeenCalledWith(4);
    expect(screen.getByRole("link", { name: "Campaign page" })).toHaveAttribute("href", "/c/laser");
  });
});

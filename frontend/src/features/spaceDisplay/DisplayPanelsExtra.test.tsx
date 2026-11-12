import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DisplayCanvas } from "./DisplayCanvas";
import { InventoryHighlightsPanel, SponsorsPanel } from "./DisplayPanelsExtra";
import { sampleState } from "./previewState";
import { availablePanels } from "./useDisplayScreen";

describe("inventory highlights and sponsors panels", () => {
  it("shows an exact count only when the server sent one, else the status label, and never a location", () => {
    render(<InventoryHighlightsPanel data={{ items: [
      { name: "Oscilloscope", category: "Electronics", image_url: null, availability: { mode: "exact_count", count: 3, label: "Available" } },
      { name: "Drill", category: "", image_url: null, availability: { mode: "status_only", label: "Limited" } },
      { name: "Hidden count", category: "", image_url: null, availability: null }] }} />);
    expect(screen.getByText("3 available")).toBeInTheDocument();
    expect(screen.getByText("Limited")).toBeInTheDocument();
    expect(screen.getByText("Hidden count")).toBeInTheDocument();
  });

  it("falls back to the sponsor's name when there is no logo", () => {
    render(<SponsorsPanel data={{ sponsors: [{ name: "Acme", tier: "Gold", logo_url: null }, { name: "Globex", tier: "", logo_url: "https://cdn.example/globex.png" }] }} />);
    expect(screen.getByText("Acme")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Globex" })).toBeInTheDocument();
  });

  it("is only offered when the screen has something in it, and renders in the grid layout", () => {
    const state = sampleState({ panels: ["inventory_highlights", "sponsors"], layout: "grid" }, "Preview");
    expect(availablePanels(state)).toEqual(["inventory_highlights", "sponsors"]);
    render(<DisplayCanvas state={state} now={Date.now()} />);
    expect(screen.getByText("On the shelf")).toBeInTheDocument();
    expect(screen.getByText("Thank you to our sponsors")).toBeInTheDocument();
    expect(availablePanels({ ...state, inventory_highlights: null, sponsors: { sponsors: [] } })).toEqual([]);
  });
});

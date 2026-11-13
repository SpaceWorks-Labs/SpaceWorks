import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { MakerspacePicker } from "./MakerspacePicker";
import type { Makerspace } from "./StaffPanels";

const makerspaces = [
  { id: 1, name: "Studio Alpha", public_code: "ALFA", slug: "alpha" },
  { id: 2, name: "Studio Beta", public_code: "BETA", slug: "beta" },
] as Makerspace[];

describe("makerspace picker", () => {
  it("searches existing spaces by name, code or slug and selects the scoped id", () => {
    const onSelect = vi.fn();
    render(<MemoryRouter><MakerspacePicker makerspaces={makerspaces} loading={false} username="Sam" onSelect={onSelect} onSignOut={vi.fn()} /></MemoryRouter>);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByText("Studio Beta")).toBeVisible();
    fireEvent.change(screen.getByLabelText("Name, code or slug"), { target: { value: "ALFA" } });
    expect(screen.queryByText("Studio Beta")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Studio Alpha/ }));
    expect(onSelect).toHaveBeenCalledWith(1);
    fireEvent.change(screen.getByLabelText("Name, code or slug"), { target: { value: "unknown" } });
    expect(screen.getByText("No spaces match. Try another name, code or slug.")).toBeVisible();
  });
});

import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { LayerEditor } from "./LayerEditor";
import type { LayerDocument } from "./layout";

const start: LayerDocument = { version: 2, page_width_mm: 297, page_height_mm: 210, layers: [
  { id: "a", order: 0, type: "text", x_mm: 10, y_mm: 10, width_mm: 60, height_mm: 12, rotation: 0, text: "{{name}}" },
  { id: "b", order: 1, type: "certificate_qr", x_mm: 250, y_mm: 160, width_mm: 25, height_mm: 25, rotation: 0, resource_slot: "certificate_verification_qr" },
] };

function Harness({ spy, kind = "certificate" as const }: { spy: (doc: LayerDocument) => void; kind?: "certificate" | "badge" }) {
  const [doc, setDoc] = useState(start);
  return <LayerEditor kind={kind} document={doc} values={{ name: "Priya Raman" }} onChange={(next) => { spy(next); setDoc(next); }} />;
}

describe("LayerEditor", () => {
  it("moves, rotates and deletes the selected layer from the keyboard, with undo", () => {
    const spy = vi.fn();
    render(<Harness spy={spy} />);
    const text = screen.getByRole("button", { name: /Text "{{name}}"\. Arrow keys/ });
    fireEvent.keyDown(text, { key: "ArrowRight", shiftKey: true });
    expect(spy.mock.lastCall?.[0].layers[0].x_mm).toBe(15);
    fireEvent.keyDown(text, { key: "]", shiftKey: true });
    expect(spy.mock.lastCall?.[0].layers[0].rotation).toBe(15);
    fireEvent.click(screen.getByRole("button", { name: "Undo" }));
    expect(spy.mock.lastCall?.[0].layers[0].rotation).toBe(0);
    fireEvent.keyDown(text, { key: "Delete" });
    expect(spy.mock.lastCall?.[0].layers).toHaveLength(1);
    expect(screen.getByRole("status").textContent).toMatch(/No visible layer prints/);
  });

  it("locks layers, refuses to hide the verification QR and offers certificate merge tags", () => {
    const spy = vi.fn();
    render(<Harness spy={spy} />);
    expect(screen.getByRole("button", { name: "2. Verification QR always prints" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: /Lock 1\./ }));
    expect(spy.mock.lastCall?.[0].layers[0].locked).toBe(true);
    expect(screen.getByRole("button", { name: /Unlock 1\./ })).toBeInTheDocument();
  });

  it("aligns to the page and shows the merged sample on the canvas", () => {
    const spy = vi.fn();
    render(<Harness spy={spy} />);
    expect(screen.getAllByText("Priya Raman").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "Centre on page horizontally" }));
    expect(spy.mock.lastCall?.[0].layers[0].x_mm).toBe(118.5);
    expect(screen.getByRole("button", { name: "{{award}}" })).toBeInTheDocument();
  });

  it("keeps badge merge tags to the badge set", () => {
    render(<Harness spy={vi.fn()} kind="badge" />);
    expect(screen.queryByRole("button", { name: "{{award}}" })).toBeNull();
    expect(screen.getByRole("button", { name: "{{crewRole}}" })).toBeInTheDocument();
  });
});

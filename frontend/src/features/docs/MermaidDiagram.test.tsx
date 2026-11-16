import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MermaidDiagram, naturalSize } from "./MermaidDiagram";

const SVG = '<svg viewBox="0 0 1200 800" width="100%"><g/></svg>';
vi.mock("mermaid", () => ({ default: { initialize: vi.fn(), render: vi.fn(async () => ({ svg: SVG })) } }));

describe("naturalSize", () => {
  it("reads the viewBox", () => expect(naturalSize(SVG)).toEqual({ width: 1200, height: 800 }));
  it("returns null without a viewBox", () => expect(naturalSize("<svg></svg>")).toBeNull());
});

describe("MermaidDiagram", () => {
  it("keeps a readable minimum width inline and opens a labelled full-size dialog", async () => {
    render(<MermaidDiagram code="flowchart TD; A-->B" />);
    const open = await screen.findByRole("button", { name: /full size/i });
    const inline = screen.getByRole("img", { name: /diagram/i });
    expect(inline.style.getPropertyValue("--diagram-min")).toBe("900px");
    fireEvent.click(open);
    const dialog = await screen.findByRole("dialog", { hidden: true });
    expect(dialog.querySelector("svg")).not.toBeNull();
    const close = screen.getByRole("button", { name: /close full-size/i, hidden: true });
    fireEvent.click(close);
    await waitFor(() => expect(document.querySelector("dialog")).toBeNull());
  });
});

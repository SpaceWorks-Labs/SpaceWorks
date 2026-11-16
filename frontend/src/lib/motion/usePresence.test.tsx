import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useExitingItems, usePresence } from "./usePresence";

function Panel({ open }: { open: boolean }) {
  const presence = usePresence(open, 100);
  return presence.present ? <div data-testid="panel" data-state={presence.state} onAnimationEnd={presence.onAnimationEnd} /> : null;
}

function List({ ids }: { ids: number[] }) {
  const rows = useExitingItems(ids, id => id, 100);
  return <ul>{rows.map(({ item, leaving }) => <li key={item} data-leaving={leaving}>{item}</li>)}</ul>;
}

const doc = document as unknown as { getAnimations?: () => unknown[] };

describe("exit animations", () => {
  afterEach(() => { delete doc.getAnimations; vi.useRealTimers(); vi.unstubAllGlobals(); });

  it("unmounts immediately where animations do not run (jsdom, tests)", () => {
    const view = render(<Panel open />);
    expect(screen.getByTestId("panel")).toHaveAttribute("data-state", "open");
    view.rerender(<Panel open={false} />);
    expect(screen.queryByTestId("panel")).toBeNull();
  });

  describe("with animation support", () => {
    beforeEach(() => { vi.useFakeTimers(); doc.getAnimations = () => []; vi.stubGlobal("matchMedia", () => ({ matches: false })); });

    it("keeps the panel in its closed state until the safety timer, then removes it", () => {
      const view = render(<Panel open />);
      view.rerender(<Panel open={false} />);
      expect(screen.getByTestId("panel")).toHaveAttribute("data-state", "closed");
      act(() => { vi.advanceTimersByTime(200); });
      expect(screen.queryByTestId("panel")).toBeNull();
    });

    it("unmounts as soon as the exit animation ends", () => {
      const view = render(<Panel open />);
      view.rerender(<Panel open={false} />);
      // jsdom exposes only the vendor-prefixed style props, so React listens for the prefixed event name here.
      const panel = screen.getByTestId("panel");
      fireEvent.animationEnd(panel);
      fireEvent(panel, new Event("webkitAnimationEnd", { bubbles: true }));
      expect(screen.queryByTestId("panel")).toBeNull();
    });

    it("cancels the exit when reopened mid-way", () => {
      const view = render(<Panel open />);
      view.rerender(<Panel open={false} />);
      view.rerender(<Panel open />);
      act(() => { vi.advanceTimersByTime(300); });
      expect(screen.getByTestId("panel")).toHaveAttribute("data-state", "open");
    });

    it("does not animate under reduced motion", () => {
      vi.stubGlobal("matchMedia", (query: string) => ({ matches: query.includes("reduce") }));
      const view = render(<Panel open />);
      view.rerender(<Panel open={false} />);
      expect(screen.queryByTestId("panel")).toBeNull();
    });

    it("keeps removed list rows flagged as leaving, then drops them", () => {
      const view = render(<List ids={[1, 2]} />);
      view.rerender(<List ids={[2]} />);
      expect(screen.getByText("1")).toHaveAttribute("data-leaving", "true");
      expect(screen.getByText("2")).toHaveAttribute("data-leaving", "false");
      act(() => { vi.advanceTimersByTime(300); });
      expect(screen.queryByText("1")).toBeNull();
    });
  });

  it("removes list rows immediately without animation support", () => {
    const view = render(<List ids={[1, 2]} />);
    view.rerender(<List ids={[2]} />);
    expect(screen.queryByText("1")).toBeNull();
  });
});

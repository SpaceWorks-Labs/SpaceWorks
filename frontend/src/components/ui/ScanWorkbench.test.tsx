import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { expectNoA11yViolations } from "../../test/axe";
import { ScanWorkbench } from "./ScanWorkbench";
vi.mock("./QrScanner", () => ({ default: ({ onScan, onClose }: { onScan: (value: string) => void; onClose: () => void }) =>
  <div role="dialog" aria-label="Camera"><button onClick={() => onScan("BOX-0042")}>Read QR</button><button onClick={onClose}>Close camera</button></div> }));
it("supports paste/find, user-initiated camera, results and recent Undo", async () => {
  const find = vi.fn(), scan = vi.fn(), undo = vi.fn();
  const { container } = render(<ScanWorkbench onFind={find} onScan={scan}
    result={{ tone: "success", title: "Tool found", next: { label: "Next", onClick: vi.fn() } }}
    recent={[{ key: "drill", label: "Drill scanned", meta: "Just now · QR", undo: { label: "Undo", onClick: undo } }]} />);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Find" })).toBeDisabled();
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "  drill  " } });
  fireEvent.click(screen.getByRole("button", { name: "Find" })); expect(find).toHaveBeenCalledWith("drill");
  fireEvent.click(screen.getByRole("button", { name: "Start scanning" }));
  fireEvent.click(screen.getByRole("button", { name: "Read QR" })); expect(scan).toHaveBeenCalledWith("BOX-0042");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Undo" })); expect(undo).toHaveBeenCalledOnce();
  await expectNoA11yViolations(container);
});
it("keeps the paste path and reports loading, retry and empty results", () => {
  const retry = vi.fn();
  const { rerender } = render(<ScanWorkbench onFind={vi.fn()} state={{ status: "loading" }} />);
  expect(screen.getByRole("status", { name: "Loading scanner" })).toBeInTheDocument();
  rerender(<ScanWorkbench onFind={vi.fn()} state={{ status: "error", error: "Offline", onRetry: retry }} />);
  fireEvent.click(screen.getByRole("button", { name: "Retry" })); expect(retry).toHaveBeenCalledOnce();
  rerender(<ScanWorkbench onFind={vi.fn()} />);
  expect(screen.getByText("Scan a QR code or find an item to get started.")).toBeInTheDocument();
});

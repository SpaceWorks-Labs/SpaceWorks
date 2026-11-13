import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { PrintStatusPanel } from "./PublicPrintRequestPanels";

it("copies the private tracking link and confirms the result", async () => {
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
  render(<PrintStatusPanel submitted tokenStatusPending={false} tokenStatusError={null} trackingHref="https://space.test/print?token=private" />);
  fireEvent.click(screen.getByRole("button", { name: "Copy tracking link" }));
  await screen.findByText("Tracking link copied. Keep it private.");
  expect(writeText).toHaveBeenCalledWith("https://space.test/print?token=private");
});
it("offers a retry when the existing status query fails", () => {
  const retry = vi.fn();
  render(<PrintStatusPanel submitted={false} tokenStatusPending={false} tokenStatusError={new Error("server")} onRetry={retry} />);
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(retry).toHaveBeenCalledOnce();
});

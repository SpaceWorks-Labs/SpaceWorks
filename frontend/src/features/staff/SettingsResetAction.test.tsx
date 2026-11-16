import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { SettingsResetAction } from "./SettingsResetAction";

it("names the credential reset and waits for confirmation before sending it", async () => {
  const reset = vi.fn().mockResolvedValue(undefined);
  render(<SettingsResetAction label="Clear SMTP password" consequence="Email delivery may stop."
    pending={false} onConfirm={reset} />);
  fireEvent.click(screen.getByRole("button", { name: /Clear SMTP password/ }));
  expect(reset).not.toHaveBeenCalled();
  const dialog = screen.getByRole("dialog", { name: "Clear SMTP password?" });
  expect(within(dialog).getByText("Email delivery may stop.")).toBeVisible();
  fireEvent.click(within(dialog).getByRole("button", { name: "Clear SMTP password" }));
  await waitFor(() => expect(reset).toHaveBeenCalledOnce());
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
});

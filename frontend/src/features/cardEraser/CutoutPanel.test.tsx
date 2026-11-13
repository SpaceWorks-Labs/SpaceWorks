import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { memberRequest, staffRequest } from "../../lib/api";
import type { Cutout } from "./api";
import { CutoutPanel } from "./CutoutPanel";

vi.mock("../../lib/api", async (original) => ({ ...(await original<typeof import("../../lib/api")>()),
  staffRequest: vi.fn(), memberRequest: vi.fn() }));

const base: Cutout = { available: true, state: "none", error_code: "", use: "original", image_url: "", width: 0, height: 0, requested_at: null };
const show = (target: Parameters<typeof CutoutPanel>[0]["target"]) =>
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><CutoutPanel target={target} /></QueryClientProvider>);
const staff = { scope: "staff", photoPath: "/admin/member-cards/7/photo" } as const;
const member = { scope: "member", cardPath: "/member/cards/member_card/7" } as const;

describe("CutoutPanel", () => {
  beforeEach(() => { vi.mocked(staffRequest).mockReset(); vi.mocked(memberRequest).mockReset(); });

  it("is hidden when the switch is off (404), when no service is set up, and when the card has no photo", async () => {
    vi.mocked(staffRequest).mockRejectedValue(new Error("Not found"));
    const { container, unmount } = show(staff);
    await waitFor(() => expect(staffRequest).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
    unmount();
    vi.mocked(staffRequest).mockReset().mockResolvedValue({ ...base, available: false });
    const second = show(staff);
    await waitFor(() => expect(staffRequest).toHaveBeenCalled());
    expect(second.container).toBeEmptyDOMElement();
  });

  it("lets staff queue a removal without a consent box, then shows the working status", async () => {
    vi.mocked(staffRequest).mockResolvedValueOnce(base).mockResolvedValue({ ...base, state: "queued" });
    show(staff);
    fireEvent.click(await screen.findByRole("button", { name: "Remove background" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/member-cards/7/photo-cutout",
      { method: "POST", body: JSON.stringify({ consent: false }) }));
    expect(await screen.findByText("Removing the background…")).toBeVisible();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });

  it("makes a member agree first and sends that consent", async () => {
    vi.mocked(memberRequest).mockResolvedValueOnce(base).mockResolvedValue({ ...base, state: "queued" });
    show(member);
    const button = await screen.findByRole("button", { name: "Remove background" });
    expect(button).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox", { name: /I agree my photo is sent/ }));
    expect(button).toBeEnabled();
    fireEvent.click(button);
    await waitFor(() => expect(memberRequest).toHaveBeenCalledWith("/member/cards/member_card/7/photo/cutout",
      { method: "POST", body: JSON.stringify({ consent: true }) }));
  });

  it("offers Use cut-out, then Use original, and discarding", async () => {
    const done: Cutout = { ...base, state: "done", image_url: "https://files.test/c.png", width: 40, height: 60 };
    vi.mocked(staffRequest).mockResolvedValueOnce(done).mockResolvedValueOnce({ ...done, use: "cutout" })
      .mockResolvedValueOnce({ ...base });
    show(staff);
    expect(await screen.findByText("The card uses the original photo.")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Use cut-out" }));
    expect(await screen.findByText("The card uses the cut-out.")).toBeVisible();
    expect(staffRequest).toHaveBeenCalledWith("/admin/member-cards/7/photo-cutout", { method: "PATCH", body: JSON.stringify({ use: "cutout" }) });
    fireEvent.click(screen.getByRole("button", { name: "Discard cut-out" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/member-cards/7/photo-cutout", { method: "DELETE" }));
  });

  it("explains a failed job in words", async () => {
    vi.mocked(staffRequest).mockResolvedValue({ ...base, state: "failed", error_code: "no_subject_found" });
    show(staff);
    expect(await screen.findByText(/found no person in the photo/)).toBeVisible();
  });
});

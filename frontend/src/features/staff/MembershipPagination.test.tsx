import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MembershipPagination } from "./MembershipPagination";

describe("MembershipPagination", () => {
  it("uses the server's next/previous availability and moves one page", () => {
    const page = vi.fn();
    const { rerender } = render(<MembershipPagination label="members" page={1} next="next" previous={null} fetching={false} onPage={page} />);
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Next" })); expect(page).toHaveBeenCalledWith(2);
    rerender(<MembershipPagination label="members" page={2} next={null} previous="previous" fetching onPage={page} />);
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled(); expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });
});

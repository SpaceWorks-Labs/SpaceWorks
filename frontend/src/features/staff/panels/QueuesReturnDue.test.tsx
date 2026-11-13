import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { ReturnDueModal, returnDueNoticeText } from "./QueuesModals";

const row = { id: 42 } as never;
const notice = { code: "space_closed" as const, next_open_at: "2027-01-04T03:30:00+00:00" };

function mount(props: Partial<Parameters<typeof ReturnDueModal>[0]> = {}) {
  return render(<ReturnDueModal row={row} open pending={false} error="" defaultValue="2027-01-02T12:00"
    onClose={vi.fn()} onSubmit={vi.fn()} {...props} />);
}

it("formats the next opening in the space's own time zone", () => {
  expect(returnDueNoticeText(notice, "Asia/Kolkata")).toMatch(/^Space is closed at this time — next open .*9:00/);
  expect(returnDueNoticeText({ code: "space_closed", next_open_at: null })).toBe("Space is closed at this time and has no upcoming opening.");
});

it("shows the closed-time warning for the saved due and hides it once staff edit the field", () => {
  mount({ notice, timeZone: "Asia/Kolkata" });
  expect(screen.getByRole("status")).toHaveTextContent("Space is closed at this time — next open");
  fireEvent.change(screen.getByLabelText("Return due date and time"), { target: { value: "2027-01-04T12:00" } });
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});

it("shows nothing when the due falls in open hours", () => {
  mount({ notice: null });
  expect(screen.queryByText(/Space is closed/)).not.toBeInTheDocument();
});

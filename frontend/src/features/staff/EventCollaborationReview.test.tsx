import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ListLayout } from "../../components/layouts";
import { useEventCollaborationReview } from "./EventCollaborationReview";

vi.mock("./eventCollaborationsApi", () => ({ useCollaborationInbox: () => ({ data: [{ id: 1, status: "invited" }] }) }));
vi.mock("./CollaborationInbox", () => ({ CollaborationInbox: () => <p>Event invitation details</p> }));
vi.mock("./EventSeriesCollaborationInbox", () => ({
  useSeriesCollaborationInbox: () => ({ data: [] }),
  EventSeriesCollaborationInbox: () => <p>Series invitation details</p>,
}));

function EventsWithInvitations() {
  const review = useEventCollaborationReview(3);
  return <ListLayout standalone header={{ title: "Events" }} state={{ status: "ready" }}
    empty={{ message: "No events yet." }} body={{ kind: "rows", rows: <p>Workshop</p> }}
    callout={review.callout} detail={review.detail} />;
}

describe("event collaboration layout nesting", () => {
  it("retains one main-content target when Review opens the detail drawer", async () => {
    render(<EventsWithInvitations />);
    expect(document.querySelectorAll("#main-content")).toHaveLength(1);
    fireEvent.click(await screen.findByRole("button", { name: /^Review/ }));
    expect(screen.getAllByRole("heading", { name: "Event collaborations", level: 2 })).toHaveLength(2);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByText("Event invitation details")).toBeVisible();
    expect(document.querySelectorAll("#main-content")).toHaveLength(1);
  });
});

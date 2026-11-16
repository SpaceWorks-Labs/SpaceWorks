import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api";
import { PublicBookingForm } from "./PublicBookingForm";
import type { PublicBookableSpace } from "./publicBookingsApi";

const { submission } = vi.hoisted(() => ({ submission: { current: null as unknown } }));
vi.mock("./publicBookingsApi", () => ({
  useSubmitPublicBooking: () => ({ error: submission.current, data: undefined, isPending: false, mutate: vi.fn() }),
}));
vi.mock("../payments/PricePreview", () => ({ PricePreview: () => null }));

const space = { public_token: "room", name: "Laser bay", approval_mode: "instant", custom_form: null } as unknown as PublicBookableSpace;

function shows(error: StructuredApiError) {
  submission.current = error;
  render(<PublicBookingForm makerspaceSlug="lab" space={space} showCalendar={false} />);
  return screen.getByRole("alert");
}

describe("public booking eligibility refusals", () => {
  it("explains missing machine access (decision 319)", () => {
    expect(shows(new StructuredApiError(403, { code: "no_machine_access" })))
      .toHaveTextContent("A space manager has not given you access to this machine yet. Ask space staff to give you access, then try again.");
  });

  it("explains expired machine access", () => {
    expect(shows(new StructuredApiError(403, { code: "machine_access_expired" })))
      .toHaveTextContent("Your access to this machine has ended. Ask space staff to renew it, then try again.");
  });

  it("tells a non-member how to qualify", () => {
    expect(shows(new StructuredApiError(403, { code: "membership_required", detail: "An active membership is required." })))
      .toHaveTextContent(/active membership of this space\. Join or renew from your member area/);
  });

  it("keeps the overlap message for a booking conflict", () => {
    expect(shows(new StructuredApiError(409, { code: "booking_conflict", detail: "Taken." })))
      .toHaveTextContent("That time now overlaps a confirmed booking.");
  });
});

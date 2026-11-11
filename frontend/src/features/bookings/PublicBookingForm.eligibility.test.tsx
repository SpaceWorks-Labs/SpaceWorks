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
  it("explains a machine certification requirement and names it", () => {
    expect(shows(new StructuredApiError(403, { code: "certification_required", certifications: ["Laser induction"] })))
      .toHaveTextContent("You need machine training or certification first (Laser induction). Ask space staff how to qualify, then try again.");
  });

  it("explains a certification requirement without names", () => {
    expect(shows(new StructuredApiError(403, { code: "certification_required" })))
      .toHaveTextContent("You need machine training or certification first. Ask space staff how to qualify, then try again.");
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

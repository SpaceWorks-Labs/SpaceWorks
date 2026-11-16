import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { BookingPass } from "./BookingPass";
import { BookingResult } from "./BookingResult";

it("maps persisted booking check-in and neutral repeated results", () => {
  const result = render(<BookingPass name="Alex" title="Laser booking" checkedInAt={null} />);
  expect(screen.getByText("Ready for check-in")).toBeTruthy();
  result.rerender(<BookingPass name="Alex" title="Laser booking" checkedInAt="2026-10-18T10:00:00Z" />);
  expect(screen.getByText("Checked in")).toBeTruthy();
  expect(result.container.querySelector("time")).toHaveAttribute("datetime", "2026-10-18T10:00:00Z");
  result.rerender(<BookingResult resultId="persisted-result" name="Alex" outcome="already_checked_in" />);
  expect(screen.getByText("Already checked in.")).toBeTruthy();
});

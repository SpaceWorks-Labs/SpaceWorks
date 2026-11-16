import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { LoanPass } from "./LoanPass";
import { LoanResult } from "./LoanResult";

it("maps persisted issue and return timestamps and clear blocked errors", () => {
  const result = render(<LoanPass title="Drill loan" issuedAt="2026-10-18T10:00:00Z" returnedAt={null} />);
  expect(screen.getByText("Issued")).toBeTruthy();
  result.rerender(<LoanPass title="Drill loan" issuedAt="2026-10-18T10:00:00Z" returnedAt="2026-10-18T12:00:00Z" />);
  expect(screen.getByText("Returned")).toBeTruthy();
  expect(result.container.querySelector("time")).toHaveAttribute("datetime", "2026-10-18T12:00:00Z");
  result.rerender(<LoanResult resultId="persisted-result" name="Alex" outcome="blocked" />);
  expect(screen.getByText("Handover wasn't recorded. Review the request status.")).toBeTruthy();
});

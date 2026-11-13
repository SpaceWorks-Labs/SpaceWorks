import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PayNextStep } from "./PayNextStep";

describe("PayNextStep", () => {
  it("points at the Payments page and offers both roads once a charge is recorded", () => {
    render(<PayNextStep paymentsHref="/m/lab/member/payments" />);
    expect(screen.getByRole("link", { name: "Payments" })).toHaveAttribute("href", "/m/lab/member/payments");
    expect(screen.getByText(/pay at the space/)).toBeInTheDocument();
  });

  it("while the request waits for staff, says nothing is owed yet and links nowhere", () => {
    render(<PayNextStep paymentsHref="/x" pending />);
    expect(screen.getByText("You will only be charged if staff approve it.")).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});

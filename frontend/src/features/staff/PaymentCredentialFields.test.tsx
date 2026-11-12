import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PaymentCredentialFields } from "./PaymentCredentialFields";

// PAY-REVIEW 0.12.0: native Razorpay Orders settle only once captured, so the setup screen says so.
describe("PaymentCredentialFields", () => {
  it("tells a Razorpay space to turn on automatic capture", () => {
    render(<PaymentCredentialFields provider="razorpay" draft={{}} onChange={() => {}} disabled={false} />);
    expect(screen.getByText(/Turn on automatic capture in the Razorpay Dashboard/)).toBeVisible();
  });

  it("does not show the Razorpay capture hint for Stripe", () => {
    render(<PaymentCredentialFields provider="stripe" draft={{}} onChange={() => {}} disabled={false} />);
    expect(screen.queryByText(/automatic capture/)).toBeNull();
  });
});

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MakerspaceLoanPolicySettings } from "./MakerspaceLoanPolicySettings";

const request = vi.hoisted(() => vi.fn().mockResolvedValue({}));
vi.mock("../../lib/api", () => ({ staffRequest: request }));
vi.mock("./panels/shared", () => {
  const data = { id: 1, default_loan_days: 7, loan_renewal_mode: "auto", loan_max_renewals: 2,
    loan_renewal_days: 3, loan_max_active: 4, loan_max_items: 8, loan_reminder_offsets_hours: [0],
    loan_escalate_overdue_days: 5 };
  return { useStaffGet: () => ({ data, refetch: vi.fn() }) };
});

describe("loan policy feature visibility", () => {
  it("hides disabled controls, restores each feature independently and retains stored values on save", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const panel = (features: string[]) => <QueryClientProvider client={client}>
      <MakerspaceLoanPolicySettings makerspaceId={1} enabledFeatures={features} />
    </QueryClientProvider>;
    const { rerender } = render(panel([]));
    expect(screen.queryByLabelText("Renewal mode")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Maximum renewals")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Maximum active loans (0 = unlimited)")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Maximum outstanding items (0 = unlimited)")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Loan period in days")).toHaveValue(7);
    fireEvent.change(screen.getByLabelText("Loan period in days"), { target: { value: "9" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(request).toHaveBeenCalled());
    const sent = JSON.parse(request.mock.calls.at(-1)![1].body);
    expect(sent).toMatchObject({ default_loan_days: 9, loan_max_active: 4, loan_max_items: 8,
      loan_renewal_mode: "auto", loan_max_renewals: 2, loan_renewal_days: 3 });

    rerender(panel(["loans.renewals"]));
    expect(screen.getByLabelText("Maximum renewals")).toHaveValue(2);
    expect(screen.getByLabelText("Renewal length in days")).toHaveValue(3);
    expect(screen.getByLabelText("Renewal mode")).toHaveValue("auto");
    expect(screen.queryByLabelText("Maximum active loans (0 = unlimited)")).not.toBeInTheDocument();
    rerender(panel(["loans.limits"]));
    expect(screen.getByLabelText("Maximum active loans (0 = unlimited)")).toHaveValue(4);
    expect(screen.getByLabelText("Maximum outstanding items (0 = unlimited)")).toHaveValue(8);
    expect(screen.queryByLabelText("Renewal mode")).not.toBeInTheDocument();
  });
});

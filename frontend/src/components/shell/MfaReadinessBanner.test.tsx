import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MfaEnrollmentScreen, MfaGraceBanner } from "../../features/staff/StaffGateScreens";
import { expectNoA11yViolations } from "../../test/axe";
import { MfaReadinessBanner } from "./MfaReadinessBanner";

describe("MfaReadinessBanner", () => {
  it("names the lock date and links to enrolment", async () => {
    const endsAt = "2026-11-07T09:30:00Z";
    const when = new Date(endsAt).toLocaleString(undefined, { weekday: "long", day: "numeric", month: "long", hour: "numeric", minute: "2-digit" });
    const { container } = render(<MfaReadinessBanner endsAt={endsAt} href="/mfa?return=%2Fadmin" />);
    expect(screen.getByText("Set up two-step sign-in")).toBeInTheDocument();
    expect(screen.getByText(new RegExp(`Staff screens lock on ${when}`))).toBeInTheDocument();
    expect(screen.getByText(/Your member area keeps working/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Set it up now/ })).toHaveAttribute("href", "/mfa?return=%2Fadmin");
    await expectNoA11yViolations(container);
  });

  it("survives a bad date", () => {
    render(<MfaReadinessBanner endsAt="not-a-date" href="/mfa" />);
    expect(screen.getByText(/Staff screens lock soon/)).toBeInTheDocument();
  });

  it("is what the staff shell's grace banner renders, returning to the current page", () => {
    window.history.replaceState(null, "", "/admin/inventory?tab=2");
    render(<MfaGraceBanner endsAt="2026-11-07T09:30:00Z" />);
    expect(screen.getByRole("link", { name: /Set it up now/ })).toHaveAttribute("href", "/mfa?return=%2Fadmin%2Finventory%3Ftab%3D2");
  });
});

describe("MfaEnrollmentScreen", () => {
  it("offers a passkey beside an authenticator and keeps the member area open", async () => {
    const { container } = render(<MfaEnrollmentScreen memberHref="/member" onSignOut={vi.fn()} />);
    expect(screen.getByRole("heading", { level: 1, name: "Set up two-step sign-in" })).toBeVisible();
    const ways = screen.getByRole("list", { name: "Ways to add a second step" });
    expect(within(ways).getByText("A passkey")).toBeInTheDocument();
    expect(within(ways).getByText("An authenticator app")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to your member area" })).toHaveAttribute("href", "/member");
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
    await expectNoA11yViolations(container);
  });
});

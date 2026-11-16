import { screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { renderWorkspace, resetShellMocks } from "../../../e2e/fixtures/staffShellHarness";

beforeEach(resetShellMocks);
const nav = () => within(screen.getByRole("navigation", { name: "Staff sections" }));
// Can hand out directly, but holds neither accept_request nor issue_request, so no request queue renders.
const directDesk = ["view_inventory", "issue_direct_loan", "upload_evidence", "record_payment"];
describe("front desk without request queues", () => {
  it("lands on Home with Direct handout available and hides Requests", () => {
    renderWorkspace("/admin", { actions: directDesk });
    expect(screen.getByTestId("location")).toHaveTextContent("/m/lab/admin/dashboard");
    expect(nav().queryByRole("link", { name: "Requests" })).toBeNull();
    expect(nav().getByRole("link", { name: "Home" })).toHaveAttribute("aria-current", "page");
    expect(nav().getByRole("link", { name: "Direct handout" })).toHaveAttribute("href", "/m/lab/admin/direct-handout");
  });
  it("sends a stale Requests bookmark to Direct handout", () => {
    renderWorkspace("/m/lab/admin/requests", { actions: directDesk });
    expect(screen.getByTestId("location")).toHaveTextContent("/m/lab/admin/direct");
  });
  it("keeps Requests for a role that holds a queue action", () => {
    renderWorkspace("/m/lab/admin/requests", { actions: [...directDesk, "issue_request"] });
    expect(screen.getByTestId("location")).toHaveTextContent("/m/lab/admin/requests");
    expect(nav().getByRole("link", { name: "Requests" })).toBeInTheDocument();
  });
});

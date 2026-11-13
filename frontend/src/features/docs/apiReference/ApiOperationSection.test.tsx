import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { fixtureSpec } from "./__tests__/apiFixture";
import { buildApiReference } from "./apiReferenceModel";
import { buildCurl } from "./apiCurl";
import { ApiOperationSection } from "./ApiOperationSection";

const loans = buildApiReference(fixtureSpec).payloads.loans;
const [create, list] = loans.operations;

function renderOperation(operation = create) {
  return render(<ApiOperationSection operation={operation} schemas={loans.schemas} schemes={loans.securitySchemes} origin="https://works.example" />);
}

describe("ApiOperationSection", () => {
  it("shows the method, path, auth and the parameters table", () => {
    renderOperation();
    const section = screen.getByRole("region", { name: "Create a loan" });
    expect(section).toHaveAttribute("id", "loans_create");
    expect(within(section).getByText("POST")).toBeInTheDocument();
    expect(within(section).getByText("/api/v1/admin/makerspaces/{makerspace_id}/loans/")).toBeInTheDocument();
    expect(within(section).getByText("Sign-in required · jwtAuth")).toBeInTheDocument();
    const table = within(section).getByRole("table");
    expect(within(table).getAllByRole("row")).toHaveLength(3);
    expect(within(table).getByText("dry_run")).toBeInTheDocument();
    expect(within(table).getByText("Validate only.")).toBeInTheDocument();
    expect(within(section).getByText("Requires the issue_request action.")).toBeInTheDocument();
  });

  it("opens nested response fields on demand and stops at a cycle", async () => {
    renderOperation();
    expect(screen.getByText("LoanRequest")).toBeInTheDocument();
    expect(screen.getAllByText("required").length).toBeGreaterThan(0);
    expect(screen.getByText("requested")).toBeInTheDocument();
    expect(screen.queryByText("parts")).not.toBeInTheDocument();
    const item = screen.getAllByText("item").find(node => node.closest("summary"))!;
    fireEvent.click(item.closest("summary")!);
    const details = item.closest("details")!;
    if (!details.open) details.open = true;
    fireEvent(details, new Event("toggle"));
    const parts = await within(details).findByText("parts");
    expect(parts.closest("li")).toHaveTextContent("(same shape as above)");
    expect(parts.closest("summary")).toBeNull();
  });

  it("lists error responses and a copyable curl request", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    renderOperation();
    expect(screen.getByRole("heading", { name: "Errors" })).toBeInTheDocument();
    expect(screen.getByText("Not allowed.")).toBeInTheDocument();
    const curl = screen.getByText(/curl -X POST/);
    expect(curl.textContent).toContain("https://works.example/api/v1/admin/makerspaces/<makerspace_id>/loans/?dry_run=<dry_run>");
    expect(curl.textContent).toContain("Authorization: Bearer $SPACEWORKS_TOKEN");
    expect(curl.textContent).toContain('"item_id": 0');
    fireEvent.click(screen.getByRole("button", { name: "Copy" }));
    expect(await screen.findByRole("button", { name: "Copied" })).toBeInTheDocument();
    expect(writeText).toHaveBeenCalledWith(curl.textContent);
  });

  it("marks optional sign-in and leaves the auth header out of anonymous calls", () => {
    renderOperation(list);
    expect(screen.getByText("Sign-in optional · PublishableKey")).toBeInTheDocument();
    expect(buildCurl(list, loans.schemas, "https://works.example/")).toBe("curl -X GET 'https://works.example/api/public/<slug>/loans/'");
  });
});

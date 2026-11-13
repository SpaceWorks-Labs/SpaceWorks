import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { EMPTY_HOSTING_FORM, hostingRequestBody, type HostingFormKey } from "./hostingForm";
import { HostingRequestFields } from "./HostingRequestFields";

function Harness({ show }: { show: boolean }) {
  const [form, setForm] = useState(EMPTY_HOSTING_FORM);
  return <>
    <HostingRequestFields value={form} errors={{}} showExpectedMembers={show}
      onChange={(key: HostingFormKey, value: string) => setForm(current => ({ ...current, [key]: value }))} />
    <output data-testid="body">{JSON.stringify(hostingRequestBody(form))}</output>
  </>;
}

describe("expected members on the hosting request form", () => {
  it("sends the optional count as a number", () => {
    render(<Harness show />);
    fireEvent.change(screen.getByRole("spinbutton", { name: /Expected members/ }), { target: { value: "120" } });
    expect(JSON.parse(screen.getByTestId("body").textContent ?? "{}")).toMatchObject({ expected_members: 120 });
  });

  it("leaves the count out when blank or invalid", () => {
    expect(hostingRequestBody(EMPTY_HOSTING_FORM)).not.toHaveProperty("expected_members");
    expect(hostingRequestBody({ ...EMPTY_HOSTING_FORM, expected_members: "2.5" })).not.toHaveProperty("expected_members");
  });

  it("is not shown on the invitation form", () => {
    render(<Harness show={false} />);
    expect(screen.queryByRole("spinbutton", { name: /Expected members/ })).not.toBeInTheDocument();
  });
});

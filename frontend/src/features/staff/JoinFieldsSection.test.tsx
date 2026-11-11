import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { staffRequest } from "../../lib/api";
import { EMPTY_JOIN_FIELDS, JoinFieldsSection, joinPlanInput, type JoinPlanFields } from "./JoinFieldsSection";
import { JoinRegisterSwitches, joinRegisterSettingsSections } from "./membershipLifecycle/joinRegisterSettings";

vi.mock("../../lib/api", async (importOriginal) => ({ ...(await importOriginal<typeof import("../../lib/api")>()), staffRequest: vi.fn() }));
beforeEach(() => { vi.mocked(staffRequest).mockReset(); vi.mocked(staffRequest).mockResolvedValue({}); });

function Harness({ features }: { features: string[] }) {
  const [value, setValue] = useState<JoinPlanFields>(EMPTY_JOIN_FIELDS);
  return <><JoinFieldsSection value={value} onChange={setValue} features={features} /><output data-testid="out">{JSON.stringify(joinPlanInput(value, features))}</output></>;
}

describe("plan join-form extras (parity O-B2)", () => {
  it("renders nothing and sends nothing while both switches are off", () => {
    render(<Harness features={[]} />);
    expect(screen.queryByText("Join form extras")).toBeNull();
    expect(screen.getByTestId("out")).toHaveTextContent("{}");
  });

  it("sends only the fields whose switch is on", () => {
    render(<Harness features={["membership.join_contact_fields"]} />);
    expect(screen.queryByRole("radiogroup", { name: "Card photo" })).toBeNull();
    fireEvent.click(screen.getAllByRole("radio", { name: "Required" })[0]);
    expect(JSON.parse(screen.getByTestId("out").textContent ?? "")).toEqual({ join_phone: "required", join_state: "hidden" });
  });
});

describe("Settings › Joining and the register", () => {
  it("is offered to the Space Manager only where memberships run", () => {
    expect(joinRegisterSettingsSections({ id: 1, enabled_modules: [] }, true)).toEqual([]);
    expect(joinRegisterSettingsSections({ id: 1, enabled_modules: ["membership"] }, false)).toEqual([]);
    expect(joinRegisterSettingsSections({ id: 1, enabled_modules: ["membership"] }, true)).toHaveLength(1);
  });

  it("turns a switch on without touching the others", async () => {
    const client = new QueryClient();
    render(<QueryClientProvider client={client}><JoinRegisterSwitches space={{ id: 5, enabled_features: ["membership.units"] }} /></QueryClientProvider>);
    fireEvent.click(screen.getByLabelText("Let reviewers send an application back"));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/5",
      { method: "PATCH", body: JSON.stringify({ enabled_features: ["membership.units", "membership.ask_changes"] }) }));
  });
});

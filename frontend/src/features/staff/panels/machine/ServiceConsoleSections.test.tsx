import { fireEvent, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import type { MachineServiceRequest } from "../../../../generated/api";
import { ServiceConsoleSections, ServiceQueueTabs } from "./ServiceConsoleSections";

describe("Service queue presentation", () => {
  it("filters loaded jobs while keeping terminal history reachable", () => {
    const rows = [{ id: 1, title: "New part", status: "pending" },
      { id: 2, title: "Old part", status: "collected" }] as MachineServiceRequest[];
    render(<ServiceQueueTabs rows={rows}>{visible => <>{visible?.map(row => <p key={row.id}>{row.title}</p>)}</>}</ServiceQueueTabs>);
    expect(screen.getByText("New part")).toBeVisible();
    expect(within(screen.getByRole("tabpanel", { name: "Active 1" })).getByText("New part")).toBeVisible();
    expect(screen.queryByText("Old part")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "All jobs 2" }));
    expect(screen.getByText("Old part")).toBeVisible();
    expect(within(screen.getByRole("tabpanel", { name: "All jobs 2" })).getByText("Old part")).toBeVisible();
  });

  it("keeps failed jobs in the default Active tab so they can be reprinted", () => {
    const rows = [{ id: 1, title: "Broken print", status: "failed" }, { id: 2, title: "Old part", status: "collected" }] as MachineServiceRequest[];
    render(<ServiceQueueTabs rows={rows}>{visible => <>{visible?.map(row => <p key={row.id}>{row.title}</p>)}</>}</ServiceQueueTabs>);
    expect(within(screen.getByRole("tabpanel", { name: "Active 1" })).getByText("Broken print")).toBeVisible();
  });

  it("opens usage work in a dialog and keeps the usage history visible", () => {
    function Harness() {
      const [logging, setLogging] = useState(false);
      return <ServiceConsoleSections queue={<p>Queue contents</p>} manualForm={<label>Minutes<input /></label>}
        manualRows={<p>Previous usage</p>} logging={logging} onLogging={setLogging} />;
    }
    render(<Harness />);
    fireEvent.click(screen.getByRole("tab", { name: "Manual usage" }));
    expect(screen.getByText("Previous usage")).toBeVisible();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Log usage" }));
    expect(screen.getByRole("dialog", { name: "Log usage" })).toBeInTheDocument();
    expect(screen.getByLabelText("Minutes")).toBeVisible();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

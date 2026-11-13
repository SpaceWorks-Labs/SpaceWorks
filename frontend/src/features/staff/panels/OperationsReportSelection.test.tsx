import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { ReportSelectionProvider, SelectedReportPanel, useReportColumns } from "./OperationsReportSelection";
import type { ReportCatalogItem } from "./operationsReportsConfig";

const catalog = [{ key: "most-lent", title: "Most lent" }, { key: "top-borrowers", title: "Top borrowers" }] as ReportCatalogItem[];
function Columns() { return <p>{useReportColumns().join(",")}</p>; }
it("unmounts unrelated and redundant generic markup while keeping the selected specialist", () => {
  render(<ReportSelectionProvider selected="most-lent" columns={["product_name"]} catalog={catalog} hardware finance={false} machines={false}>
    <SelectedReportPanel title="Most lent"><p>Selected output</p><Columns /></SelectedReportPanel>
    <SelectedReportPanel title="Top borrowers"><p>Other report output</p></SelectedReportPanel>
    <SelectedReportPanel title="Most lent preview" reportKey="most-lent" generic><p>Redundant preview</p></SelectedReportPanel>
  </ReportSelectionProvider>);
  expect(screen.getByText("Selected output")).toBeInTheDocument();
  expect(screen.getByText("product_name")).toBeInTheDocument();
  expect(screen.queryByText("Other report output")).toBeNull();
  expect(screen.queryByText("Redundant preview")).toBeNull();
});
it("keeps generic output for catalog reports without a specialist", () => {
  render(<ReportSelectionProvider selected="member-retention" columns={[]} catalog={catalog} hardware finance={false} machines={false}>
    <SelectedReportPanel title="Retention preview" reportKey="member-retention" generic><p>Retention rows</p></SelectedReportPanel>
  </ReportSelectionProvider>);
  expect(screen.getByText("Retention rows")).toBeInTheDocument();
});
it("payment reconciliation has one table: the generic preview yields to its finance specialist", () => {
  render(<ReportSelectionProvider selected="payment-reconciliation" columns={[]} catalog={catalog} hardware={false} finance machines={false}>
    <SelectedReportPanel title="Payment reconciliation"><p>Specialist table</p></SelectedReportPanel>
    <SelectedReportPanel title="Payment reconciliation preview" reportKey="payment-reconciliation" generic><p>Generic table</p></SelectedReportPanel>
  </ReportSelectionProvider>);
  expect(screen.getByText("Specialist table")).toBeInTheDocument();
  expect(screen.queryByText("Generic table")).toBeNull();
});

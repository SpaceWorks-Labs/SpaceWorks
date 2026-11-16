import type { ComponentProps, ReactNode } from "react";
import {
  DirectLoanBorrowerFields, DirectLoanContainerField, DirectLoanIssueEvidence,
  DirectLoanItemLines, DirectLoanQrSection,
} from "./DirectLoanIssueFields";

type Props = {
  borrower: ComponentProps<typeof DirectLoanBorrowerFields>;
  container: ComponentProps<typeof DirectLoanContainerField>;
  items: ComponentProps<typeof DirectLoanItemLines>;
  qr: ComponentProps<typeof DirectLoanQrSection>;
  evidence: ComponentProps<typeof DirectLoanIssueEvidence>;
  children: ReactNode;
};

/** Keeps the complete counter form available within the guided task's compact view. */
export function DirectLoanCompactWork({ borrower, container, items, qr, evidence, children }: Props) {
  return <div className="grid gap-4">
    <DirectLoanBorrowerFields {...borrower} />
    <DirectLoanContainerField {...container} />
    <DirectLoanItemLines {...items} />
    <DirectLoanQrSection {...qr} />
    <DirectLoanIssueEvidence {...evidence} />
    {children}
  </div>;
}

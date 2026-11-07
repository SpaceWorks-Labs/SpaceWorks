import { t } from "@lingui/core/macro";
import type React from "react";
import { StatusPill as Pill } from "../../components/ui";

import { StructuredApiError } from "../../lib/api";
import type { ReceiptEnvelope } from "./tenantMigrationApi";

function flatten(value: unknown): string[] {
  if (typeof value === "string") return value.trim() ? [value.trim()] : [];
  if (Array.isArray(value)) return value.flatMap(flatten);
  if (value && typeof value === "object") return Object.values(value).flatMap(flatten);
  return [];
}

export function migrationError(error: unknown, field?: string) {
  if (!(error instanceof StructuredApiError)) {
    return error instanceof Error ? error.message : t`The tenant migration request failed.`;
  }
  // Field names do not survive StructuredApiError.message: it deliberately flattens
  // Object.values(body). Boundary errors therefore have to be read from body[field].
  const fieldMessages = field ? flatten(error.body[field]) : [];
  const detail = typeof error.body.detail === "string" ? error.body.detail : error.detail;
  const message = fieldMessages[0] ?? detail ?? flatten(error.body)[0] ?? "The request failed.";
  return error.code ? `${message} (${error.code})` : message;
}

export function ErrorText({ error, field }: { error: unknown; field?: string }) {
  if (!error) return null;
  return <p className="mt-2 text-sm text-danger" role="alert">{migrationError(error, field)}</p>;
}

export function StatusPill({ children, tone = "neutral" }: {
  children: React.ReactNode;
  tone?: "neutral" | "success" | "danger" | "warn";
}) {
  const text = typeof children === "string" ? children.replace(/_/g, " ").toLowerCase() : "migration status";
  return <Pill tone={tone} label={text.charAt(0).toUpperCase() + text.slice(1)} />;
}

export function parseReceipt(value: string): ReceiptEnvelope | null {
  try {
    const parsed = JSON.parse(value) as Partial<ReceiptEnvelope>;
    if (!parsed.payload || typeof parsed.payload !== "object" || Array.isArray(parsed.payload) ||
        typeof parsed.signer_fingerprint !== "string" || typeof parsed.signature !== "string") {
      return null;
    }
    return parsed as ReceiptEnvelope;
  } catch {
    return null;
  }
}

export function ReceiptOutput({ label, receipt }: { label: string; receipt?: ReceiptEnvelope }) {
  if (!receipt) return null;
  return (
    <div className="mt-3">
      <label className="text-sm font-semibold text-ink" htmlFor={`${label.replace(/\W+/g, "-")}-receipt`}>{label}</label>
      <textarea
        id={`${label.replace(/\W+/g, "-")}-receipt`}
        className="desk-input mt-1 min-h-32 w-full code-text text-base md:text-xs"
        readOnly
        value={JSON.stringify(receipt, null, 2)}
      />
    </div>
  );
}

export function openDownload(url: string) {
  const link = document.createElement("a");
  link.href = url;
  link.rel = "noopener";
  document.body.appendChild(link);
  link.click();
  link.remove();
}

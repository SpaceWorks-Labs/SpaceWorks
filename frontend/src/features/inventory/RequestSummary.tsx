import {
  StatusStepper,
  statusStageLabel,
} from "../../components/ui/StatusStepper";
import type { PublicRequestStatus } from "../../types/inventory";

export function RequestSummary({ request }: { request: PublicRequestStatus }) {
  return (
    <div className="rounded-xl border border-line bg-panel p-3 text-ink">
      <StatusStepper status={request.status} />
      <div className="flex items-start justify-between gap-3">
        <div className="mt-3">
          <p className="eyebrow text-brand-ink">Status</p>
          <p className="mt-1 tabular-nums text-base font-semibold">
            {statusStageLabel(request.status)}
          </p>
        </div>
      </div>
      {request.rejection_reason ? (
        <p className="mt-2 text-sm text-danger">{request.rejection_reason}</p>
      ) : null}
      {request.requested_for ? (
        <p className="mt-2 line-clamp-2 text-sm text-muted">
          {request.requested_for}
        </p>
      ) : null}
      <div className="mt-3 space-y-1">
        {request.items.map((item) => (
          <div
            className="flex justify-between gap-3 text-sm text-muted"
            key={`${request.public_token ?? request.created_at}-${item.product_name}`}
          >
            <span>{item.product_name}</span>
            <span className="tabular-nums">x{item.requested_quantity}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

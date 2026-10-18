import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { CenteredCardLayout } from "../../../components/layouts";
import { publicV1Request } from "../../../lib/api";

type Verification = { event: string; date: string; status: "valid" | "revoked" };

export function CertificateVerificationPage() {
  const { verificationId = "" } = useParams();
  const validId = /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i.test(verificationId);
  const query = useQuery({ queryKey: ["certificate-verification", verificationId],
    queryFn: () => publicV1Request<Verification>(`/public/event-certificates/${verificationId}/verify/`),
    enabled: validId, staleTime: 0, gcTime: 0, retry: false, refetchOnWindowFocus: true });
  return <CenteredCardLayout title="Certificate verification" eyebrow="Space Works"
    state={query.isLoading ? { status: "loading" } : { status: "ready" }}
    body={query.data ? "This check confirms the event, date and certificate status." : "This certificate is not available for public verification."}
    content={query.data ? <dl className="grid gap-3 rounded-control border border-line p-4">
      <div><dt className="text-sm text-muted">Event</dt><dd className="font-semibold text-ink">{query.data.event}</dd></div>
      <div><dt className="text-sm text-muted">Date</dt><dd className="text-ink">{query.data.date}</dd></div>
      <div><dt className="text-sm text-muted">Status</dt><dd className={query.data.status === "valid" ? "text-success-ink" : "text-danger"}>{query.data.status === "valid" ? "Valid" : "Revoked"}</dd></div>
    </dl> : query.error ? <p role="status" className="text-sm text-muted">Unknown, private and pending certificates have the same unavailable result.</p> : null}
    primary={{ label: "Space Works home", href: "/" }} />;
}

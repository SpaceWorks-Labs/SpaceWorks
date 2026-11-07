import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { CenteredCardLayout } from "../../../components/layouts";
import { publicV1Request } from "../../../lib/api";
import { AppShell } from "../../../components/shell";
import { CertificateFileCheck, shortFingerprint } from "./CertificateFileCheck";

/** The public answer for one certificate (C9). Mirrors backend certificates/output_serializers.VerificationSerializer. */
export type CertificateVerification = { event: string; date: string; status: "valid" | "revoked"; issuer: string; kind: string;
  kind_title: string; award: string; recipient_name: string | null; status_note: string; serial: string; sha256: string };

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="grid gap-0.5 sm:grid-cols-[9rem_minmax(0,1fr)] sm:gap-3"><dt className="text-sm text-muted">{label}</dt><dd className="min-w-0 break-words text-ink">{children}</dd></div>;
}

export function CertificateVerificationPage() {
  const { verificationId = "" } = useParams();
  const validId = /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i.test(verificationId);
  const query = useQuery({ queryKey: ["certificate-verification", verificationId],
    queryFn: () => publicV1Request<CertificateVerification>(`/public/event-certificates/${verificationId}/verify/`, { cache: "no-store" }),
    enabled: validId, staleTime: 0, gcTime: 0, retry: false, refetchOnWindowFocus: true });
  useEffect(() => {
    // The page is never indexed; a link preview uses the server's share image instead.
    const meta = document.createElement("meta");
    meta.name = "robots"; meta.content = "noindex";
    document.head.appendChild(meta);
    return () => meta.remove();
  }, []);
  const data = query.data;
  const valid = data?.status === "valid";
  return <AppShell variant="member" compactNav="drawer" activeKey="verify" nav={[]} user={{ name: "Space Works", menu: [{ label: t`Home`, href: "/" }] }}>
    <CenteredCardLayout standalone={false} width={480} title={data ? data.kind_title : t`Certificate check`} eyebrow={t`Certificate verification`}
      media={data ? { icon: valid ? "ShieldCheck" : "ShieldAlert", tone: valid ? "success" : "danger" } : undefined}
      state={query.isLoading ? { status: "loading" } : { status: "ready" }}
      body={data ? <span className={valid ? "text-success-ink" : "text-danger"}><strong>{valid ? t`Valid.` : t`Withdrawn.`}</strong> {data.status_note}</span>
        : t`This certificate is not available for public checking.`}
      content={data ? <div className="grid gap-6">
        <dl className="grid gap-3 rounded-control border border-line p-4">
          {data.recipient_name ? <Row label={t`Awarded to`}><span className="font-semibold">{data.recipient_name}</span></Row> : null}
          <Row label={t`Certificate`}>{data.kind_title}{data.award ? <><br /><span className="font-semibold">{data.award}</span></> : null}</Row>
          <Row label={t`Event`}><span className="font-semibold">{data.event}</span></Row>
          <Row label={t`Date`}>{new Date(`${data.date}T00:00:00`).toLocaleDateString(formatLocale(), { day: "numeric", month: "long", year: "numeric" })}</Row>
          <Row label={t`Issued by`}>{data.issuer}</Row>
          <Row label={t`Status`}><span className={valid ? "font-semibold text-success-ink" : "font-semibold text-danger"}>{valid ? t`Valid` : t`Revoked`}</span></Row>
          <Row label={t`Certificate ID`}><span className="font-mono text-sm">{data.serial}</span></Row>
          <Row label={t`File fingerprint`}><span className="font-mono text-sm" title={data.sha256}>{shortFingerprint(data.sha256)}</span></Row>
        </dl>
        {!data.recipient_name ? <p className="text-sm text-muted">{t`The holder has not chosen to show their name here.`}</p> : null}
        <CertificateFileCheck expected={data.sha256} />
      </div> : query.error || !validId ? <p role="status" className="text-sm text-muted">{t`Unknown, private and unfinished certificates all give this same answer.`}</p> : null}
      primary={{ label: t`Space Works home`, href: "/" }} />
  </AppShell>;
}

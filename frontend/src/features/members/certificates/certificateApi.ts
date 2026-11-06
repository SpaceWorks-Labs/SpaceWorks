import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { memberRequest, memberRequestBlob } from "../../../lib/api";

export type HolderCertificate = { id: number; event_id: number; event_title: string; event_date: string; issuer_name: string;
  kind: string; kind_title: string; award: string; status: "pending" | "rendering" | "active" | "failed" | "revoked";
  issued_at: string; revision: number; serial: string; verifiable: boolean; verify_url: string | null; holder_name_public: boolean };

const base = (makerspaceId: number) => `/member/makerspaces/${makerspaceId}/certificates/`;
export const holderKey = (makerspaceId: number) => ["member", makerspaceId, "certificates"] as const;

export function useMyCertificates(makerspaceId: number) {
  return useQuery({ queryKey: holderKey(makerspaceId), queryFn: () => memberRequest<HolderCertificate[]>(base(makerspaceId)), retry: false });
}

export function useHolderName(makerspaceId: number) {
  const client = useQueryClient();
  return useMutation({ mutationFn: ({ id, show }: { id: number; show: boolean }) => memberRequest<HolderCertificate>(
    `${base(makerspaceId)}${id}/holder-name/`, { method: "POST", body: JSON.stringify({ show }) }),
  onSuccess: (row) => client.setQueryData<HolderCertificate[]>(holderKey(makerspaceId), (rows) => rows?.map((item) => item.id === row.id ? row : item)) });
}

function save(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url; link.download = filename; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Save the 300 dpi PNG or the 1200 x 627 share image of one certificate. */
export function useCertificateImage(makerspaceId: number) {
  return useMutation({ mutationFn: async ({ row, kind }: { row: HolderCertificate; kind: "png" | "share-image" }) => {
    const blob = await memberRequestBlob(`${base(makerspaceId)}${row.id}/${kind}/`);
    save(blob, kind === "png" ? `certificate-${row.serial}.png` : `certificate-${row.serial}-share.png`);
  } });
}

export function useCertificatePdf(makerspaceId: number) {
  const client = useQueryClient();
  return useMutation({ mutationFn: (id: number) => memberRequest<{ url: string }>(`/member/makerspaces/${makerspaceId}/event-certificates/${id}/download/`),
    onSuccess: async (result) => { await client.invalidateQueries({ queryKey: holderKey(makerspaceId) }); window.location.assign(result.url); } });
}

/** LinkedIn's "Add to profile" link, built in the browser. Only offered when the certificate is publicly verifiable. */
export function linkedInUrl(row: HolderCertificate) {
  const issued = new Date(row.issued_at);
  const params = new URLSearchParams({ startTask: "CERTIFICATION_NAME", name: `${row.kind_title} · ${row.event_title}`,
    organizationName: row.issuer_name, issueYear: String(issued.getFullYear()), issueMonth: String(issued.getMonth() + 1),
    certUrl: row.verify_url ?? "", certId: row.serial });
  return `https://www.linkedin.com/profile/add?${params}`;
}

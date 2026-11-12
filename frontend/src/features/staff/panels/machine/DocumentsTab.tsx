import { t } from "@lingui/core/macro";
import { ListRow, OverflowMenu } from "../../../../components/ui";
import { MachineTabContent } from "./MachineTabContent";
import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  collectionResults,
  deleteMachineDocument,
  getMachineDocuments,
  getMachineDocumentUrl,
  machineKeys,
  uploadMachineDocument,
} from "../../machinesApi";
import { BoxArt } from "../../../../components/BoxSpinner";

export function DocumentsTab({ machineId, canEdit }: { machineId: number; canEdit: boolean }) {
  const queryClient = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [docType, setDocType] = useState("manual");
  const documents = useQuery({
    queryKey: machineKeys.documents(machineId),
    queryFn: () => getMachineDocuments(machineId),
  });
  const items = collectionResults(documents.data);
  const upload = useMutation({
    mutationFn: () => {
      if (!file) throw new Error(t`Choose a document to upload`);
      return uploadMachineDocument(machineId, file, docType.trim());
    },
    onSuccess: async () => {
      setFile(null);
      setDocType("manual");
      if (fileInput.current) fileInput.current.value = "";
      await queryClient.invalidateQueries({ queryKey: machineKeys.documents(machineId) });
    },
  });
  const view = useMutation({
    mutationFn: (documentId: number) => getMachineDocumentUrl(documentId),
    onSuccess: ({ url }) => window.open(url, "_blank", "noopener,noreferrer"),
  });
  const remove = useMutation({
    mutationFn: deleteMachineDocument,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: machineKeys.documents(machineId) }),
  });

  return (
    <section>
      <h3 className="title-section mb-3">{t`Documents`}</h3>
      <MachineTabContent query={documents} resource={t`documents`} empty={!items.length} message={t`No machine documents uploaded. Upload the first document.`}>
      <div className="grid gap-2">
        {items.map((document) => (
          <ListRow key={document.id} title={document.original_filename} identity={{ kind: "icon", icon: "Wrench", tone: "neutral" }}
            meta={`${document.doc_type} · ${formatBytes(document.size_bytes)}`} right={<div className="flex flex-wrap gap-2">
              <button className="desk-button" type="button" disabled={view.isPending} onClick={() => view.mutate(document.id)}>{t`View`}</button>
              {canEdit ? <OverflowMenu actions={[{ label: t`Delete`, tone: "danger", disabled: remove.isPending, disabledReason: t`Wait for the current change to finish.`, onClick: () => remove.mutate(document.id) }]} /> : null}
            </div>} />
        ))}
      </div>
      </MachineTabContent>
      {canEdit ? (
        <form className="mt-3 grid gap-2 sm:grid-cols-[minmax(0,1fr)_10rem_auto] sm:items-end"
          onSubmit={(event) => { event.preventDefault(); upload.mutate(); }}>
          <label className="eyebrow grid gap-1">{t`File`}<input ref={fileInput} className="desk-input" type="file"
              accept=".pdf,.jpg,.jpeg,.png,.webp,.stl,.3mf,.step,.stp,.obj,.amf,.ply,.gcode,.gco,.iges,.igs,.dxf"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)} required />
          </label>
          <label className="eyebrow grid gap-1">{t`Document type`}<input className="desk-input" maxLength={16} value={docType}
              onChange={(event) => setDocType(event.target.value)} required />
          </label>
          <button className="desk-button-primary" type="submit"
            disabled={upload.isPending || !file || !docType.trim()}>
            {upload.isPending ? <><BoxArt size={16} mono />{t`Uploading...`}</> : t`Upload`}
          </button>
        </form>
      ) : null}
      {upload.error instanceof Error ? <p role="alert" className="mt-2 text-sm text-danger">{upload.error.message}</p> : null}
      {view.error instanceof Error ? <p role="alert" className="mt-2 text-sm text-danger">{view.error.message}</p> : null}
      {remove.error instanceof Error ? <p role="alert" className="mt-2 text-sm text-danger">{remove.error.message}</p> : null}
    </section>
  );
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

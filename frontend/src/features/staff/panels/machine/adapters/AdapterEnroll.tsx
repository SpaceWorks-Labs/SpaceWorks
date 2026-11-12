import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Field, Modal } from "../../../../../components/ui";
import type { EnrollmentGrant } from "../../../devicesApi";
import { DeviceEnrollmentModal } from "../../DeviceEnrollmentModal";
import { adapterErrorMessage } from "./adapterCopy";
import { adapterKeys, adaptersApi } from "./adaptersApi";
import { BoxArt } from "../../../../../components/BoxSpinner";

/** Enrol a bridge: a Device of kind "adapter". The one-time token appears once, in the shared enrolment dialog. */
export function AdapterEnroll({ makerspaceId, onClose }: { makerspaceId: number; onClose: () => void }) {
  const client = useQueryClient();
  const [name, setName] = useState("");
  const [grant, setGrant] = useState<EnrollmentGrant | null>(null);
  const enroll = useMutation({
    mutationFn: () => adaptersApi.enroll(makerspaceId, name.trim()),
    onSuccess: result => { setGrant(result.enrollment); void client.invalidateQueries({ queryKey: adapterKeys.root(makerspaceId) }); },
  });
  if (grant) return <DeviceEnrollmentModal key={grant.enrollment_id} grant={grant} onClose={onClose} />;
  return <Modal open onClose={onClose} title={t`Enrol a bridge`} footer={<div className="flex flex-wrap justify-end gap-3">
    <button type="button" className="desk-button" onClick={onClose}>{t`Cancel`}</button>
    <button type="submit" form="adapter-enroll-form" className="desk-button-primary" disabled={!name.trim() || enroll.isPending}>
      {enroll.isPending ? <><BoxArt size={16} mono />{t`Enrolling…`}</> : t`Enrol bridge`}</button>
  </div>}>
    <form id="adapter-enroll-form" className="grid gap-4" onSubmit={event => { event.preventDefault(); if (name.trim()) enroll.mutate(); }}>
      <p className="text-sm text-muted">{t`A bridge is a small program on your network that talks to your hardware for Space Works. Name it after where it lives, then copy its one-time token into the bridge.`}</p>
      <Field label={t`Bridge name`} hint={t`For example: Workshop bridge.`}>
        <input className="desk-input" required maxLength={120} value={name} onChange={event => setName(event.target.value)} />
      </Field>
      {enroll.isError ? <p role="alert" className="rounded-control border border-danger-line p-3 text-sm text-danger">{adapterErrorMessage(enroll.error)}</p> : null}
    </form>
  </Modal>;
}

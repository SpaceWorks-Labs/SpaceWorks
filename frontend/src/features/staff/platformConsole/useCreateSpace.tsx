import { t } from "@lingui/core/macro";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "../../../components/ui/toastStore";
import { staffRequest } from "../../../lib/api";
import type { Makerspace } from "../panels/shared";
import { CreateMakerspaceModal, type MakerspaceForm } from "../panels/UsersModals";
import { emptyMakerspaceForm, makerspacePayload } from "../panels/users/forms";
import { setSpaceHostingType, useHostingSwitch, type HostingType } from "../platformSpaces/limitsApi";

/** Decision 236: own (default) or hosted, offered only while hosting other makerspaces is on. */
function HostingTypeChoice({ value, onChange }: { value: HostingType; onChange: (value: HostingType) => void }) {
  return <div className="grid gap-2" role="radiogroup" aria-label={t`Hosting type`}>
    <p className="text-sm font-semibold text-ink">{t`Hosting type`}</p>
    <label className="flex min-h-11 items-start gap-3 text-sm text-ink"><input type="radio" className="mt-1" name="create-hosting-type" checked={value === "own"} onChange={() => onChange("own")} />
      <span>{t`Own space — no plan, no limits, unlimited.`}</span></label>
    <label className="flex min-h-11 items-start gap-3 text-sm text-ink"><input type="radio" className="mt-1" name="create-hosting-type" checked={value === "hosted"} onChange={() => onChange("hosted")} />
      <span>{t`Hosted space — a plan, limits, trial and hosting bills apply.`}</span></label>
  </div>;
}

/** The Spaces page's "Create makerspace": the same lifecycle API and wizard as Staff & roles. */
export function useCreateSpace() {
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<MakerspaceForm>(emptyMakerspaceForm);
  const [hostingType, setHostingType] = useState<HostingType>("own");
  const hosting = useHostingSwitch();
  const hostingOn = hosting.data?.enabled === true;
  const create = useMutation({
    mutationFn: () => staffRequest<Makerspace>("/admin/makerspaces", { method: "POST", body: JSON.stringify(makerspacePayload(form)) }, "platform"),
    onSuccess: async result => {
      setOpen(false); setForm(emptyMakerspaceForm);
      // A new space is "own" unless chosen otherwise; a failed second step leaves it own (the safe side).
      if (hostingOn && hostingType === "hosted") {
        try { await setSpaceHostingType(result.id, "hosted"); } catch { toast(t`${result.name} was created as an own space. Set it to hosted in its details.`); }
      }
      setHostingType("own");
      toast(`${result.name} created.`);
      void client.invalidateQueries({ queryKey: ["staff", "makerspaces"] });
      void client.invalidateQueries({ queryKey: ["organizations"] });
      void client.invalidateQueries({ queryKey: ["platform-space-health"] });
    },
  });
  const start = () => { create.reset(); setOpen(true); };
  // Mounted only while open: the wizard reads organizations as soon as it renders.
  const modal = open && <CreateMakerspaceModal open form={form} pending={create.isPending} error={create.error}
    onChange={setForm} onClose={() => setOpen(false)} onSubmit={() => create.mutate()}
    identityExtra={hostingOn ? <HostingTypeChoice value={hostingType} onChange={setHostingType} /> : undefined} />;
  return { start, modal };
}

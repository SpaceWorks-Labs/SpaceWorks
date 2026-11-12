// The one staff-card design, opened in the same free designer the member cards use (domain staff_cards).
import { t } from "@lingui/core/macro";

import { CardDesigner } from "../../../../components/card-designer/CardDesigner";
import { ErrorBlock } from "../../../../components/ui";
import { useStaffCardDesign } from "./api";
import { LogoLoader } from "../../../../components/LogoLoader";

export function StaffCardDesign({ makerspaceId }: { makerspaceId: number }) {
  const design = useStaffCardDesign(makerspaceId);
  if (design.isLoading) return <LogoLoader size={48} className="min-h-64 py-3" />;
  if (design.isError || !design.data) return <ErrorBlock error={design.error} resource={t`the staff card design`} onRetry={() => void design.refetch()} />;
  return <div className="grid gap-3">
    <p className="text-sm text-muted">{t`Staff cards print the published design, or a plain Classic card with a STAFF band until you publish one. Place Name, Number, Role and Space from the data fields.`}</p>
    <CardDesigner designId={design.data.id} makerspaceId={makerspaceId} canEdit={design.data.can_edit} title={t`Staff card design`} />
  </div>;
}

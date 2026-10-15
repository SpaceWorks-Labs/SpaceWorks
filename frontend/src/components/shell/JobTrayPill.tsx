import { JobTray } from "../ui/JobTray";

export function JobTrayPill({ makerspaceId }: { makerspaceId: number }) {
  return <JobTray makerspaceId={makerspaceId} presentation="pill" />;
}

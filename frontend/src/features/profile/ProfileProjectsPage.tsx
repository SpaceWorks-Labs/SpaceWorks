import { t } from "@lingui/core/macro";
import { useState } from "react";
import { ErrorBlock, Pagination, Skeleton } from "../../components/ui";
import { ProfileProjectsTab } from "./ProfileSectionTabs";
import { usePublicProfileProjects, type PublicProject } from "./publicProfileApi";

/** The preview uses saved editor data; the live tab reads every public project page. */
export function ProfileProjectsPage({ handle, preview, projects, visible, addHref }: {
  handle: string; preview: boolean; projects: PublicProject[]; visible: boolean; addHref?: string;
}) {
  const [page, setPage] = useState(1);
  const query = usePublicProfileProjects(handle, page, !preview && visible);
  if (preview || !visible) return <ProfileProjectsTab projects={projects} addHref={addHref} />;
  return <div className="grid gap-4">
    {query.isLoading ? <Skeleton aria-label={t`Loading projects`} className="h-48" /> : null}
    {query.error ? <ErrorBlock error={new Error(t`Couldn't load projects. Try again.`)}
      onRetry={() => { void query.refetch(); }} /> : null}
    {query.data ? <>
      <ProfileProjectsTab projects={query.data.results} addHref={addHref} />
      <Pagination page={page} pageSize={24} count={query.data.count}
        totalPages={Math.ceil(query.data.count / 24)} onChange={setPage} />
    </> : null}
  </div>;
}

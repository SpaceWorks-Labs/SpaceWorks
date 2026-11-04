import { useQuery } from "@tanstack/react-query";
import { DeploymentPanel } from "../deployment/DeploymentPanel";
import { getPlatformDashboard } from "./platformMonitoringApi";
import { SettingsQueryState } from "./SettingsQueryState";

export function PlatformDeploymentSection() {
  const query = useQuery({ queryKey: ["platform-dashboard"], queryFn: getPlatformDashboard });
  return <SettingsQueryState query={query} resource="deployment information">
    {query.data?.deployment ? <DeploymentPanel data={query.data.deployment} /> : null}
  </SettingsQueryState>;
}

import { t } from "@lingui/core/macro";
import { Cog, Cpu, Wrench } from "lucide-react";
import type { CataloguePart } from "./types";

/** Machines and Connected devices groups. */
export const machinesAndDevices = (): CataloguePart => ({
  machines: { icon: Cog, value: t`Printers, lasers and CNC: access, jobs and upkeep.`,
    what: t`A registry of your machines with job queues, quotes and pickup, machine access given by a space manager, usage sessions and maintenance by date or hours of use.`,
    roles: [t`Machine managers`, t`Members`, t`Supervisors`, t`Technicians`],
    
    
    
    integrations: [t`Online payments for jobs`, t`Calendar feed for maintenance`, t`Device adapters`],
    newIn: [t`Machine access grants: a space manager gives access per machine and person`] },
  machine_service: { icon: Wrench, value: t`Service requests for every machine type, from intake to pickup.`,
    what: t`Structured intake forms, quotes, status updates and pickup for jobs the space runs for others, on any machine type: 3D printers, lasers, CNC and cutters. The 3D print queue is one machine type here, with file uploads and filament tracking.`,
    roles: [t`Technicians`, t`Machine managers`, t`Members`, t`Public requesters`],
    integrations: [t`Online payments`, t`Email and chat alerts`, t`Printer fleet adapters`, t`File formats (STL, 3MF)`],
    newIn: [t`The 3D print queue is part of Machine service: one module for every machine type`] },
  devices: { icon: Cpu, value: t`Printers, media players and adapters with their own keys.`,
    what: t`A device proves it holds its own key on every request and is never a staff account. Adapters bridge video, audio and media players, a shelf pointer and kiosk checkout stations, and report telemetry.`,
    roles: [t`Space managers`, t`Superadmins`],
    
    
    integrations: [t`Video, audio and media adapters`, t`Shelf pointer`, t`Kiosk checkout`, t`Label printers`],
    newIn: [t`Device adapters for video, audio and media`, t`Shelf pointer and kiosk checkout`] },
});

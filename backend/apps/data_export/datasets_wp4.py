from .types import TenantPredicate as P

DATASET_SPECS = {
    "machines.MachineMaterial": ("machines/materials.csv", P(("makerspace",), ("machine_type__makerspace",))),
    "operations.StocktakePolicy": ("stocktake/policy.csv", P(("makerspace",))),
    "operations.StocktakeSchedule": ("stocktake/schedules.csv", P(("makerspace",), ("container__makerspace",))),
    "machines.MachineTypeConsumable": ("machines/type_consumables.csv", P(("makerspace",))),
    "machines.ServiceRequestConsumableUsage": ("machines/job_consumable_usage.csv",
                                               P(("makerspace",), ("service_request__makerspace",))),
    "machines.MachineTypeTemplate": ("machines/type_templates.csv", P(("makerspace",))),
    "machines.MachineTypeSetup": ("machines/type_setup.csv", P(("makerspace",))),
    "machines.MachineTypeDocument": ("machines/type_documents.csv", P(("makerspace",))),
}

"""Cost-source identities remap with the finalized domain rows they measure."""

COST_SOURCE_MODELS = {
    "pooled_service": "machines.MachineServiceRequest",
    "manual_adjustment": "machines.MachineConsumableAdjustment",
    "non_pool_consumption": "machines.ServiceRequestConsumption",
    # A shop sale of a linked inventory consumable, and the restock that reverses part of it.
    "shop_sale": "shop.ShopStockMovement",
    "shop_return": "shop.ShopStockMovement",
}

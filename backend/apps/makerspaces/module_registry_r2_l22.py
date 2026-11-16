from .module_registry_definitions import GROUP_SHOP, GUARD, ModuleDefinition

# Release 2 L22 (#128 C-7, #129, #135 Q-S1): each space may run its own shop. Off by default;
# every shop feature is its own capability under it (#135), and every sale is a ledger charge.
MODULES = (ModuleDefinition(
    "shop", "Shop",
    "A per-space shop: catalogue, stock, front-desk sales and online orders for pickup, every sale "
    "in the finance ledger.",
    "shop", GUARD, group=GROUP_SHOP,
),)

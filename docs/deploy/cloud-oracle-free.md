# Oracle Always Free VM: host/full

Price never selects a weaker recovery contract. The installer's opt-in `--profile free` is a separate
choice for the single-process managed stack ([cloud-free.md](cloud-free.md)); this page keeps the full profile. An Oracle VM uses host/full and the same reviewed VPS installer
and H1 stack as paid hosts. It does not use the managed free profile or HTTP tick. Deployed acceptance and actual amd64/arm64
install/upgrade acceptance must land before qualification. Release metadata declares both architectures;
a cross-build declaration alone is not native runtime proof.

Read deploy/cloud/oracle-always-free.json and [self-hosting](../self-hosting.md). Verify the actual tenancy's
Always Free allocation, region capacity, architecture, disk/egress allowances, card/signup and reclaim policy.
Older published OCPU/memory figures are not an entitlement. These checks have not run for an owner account.
Set budgets/alerts and explicitly exclude trial/paid resources from a $0 claim.

Install a reviewed immutable release on a supported Ubuntu VM using the installer's versioned answers contract.
Keep continuity secrets and explicit scanner policy on upgrade. Verify permissions, TLS, actual mail, uploads,
installed programmes and full backup/offsite/restore acceptance. Keep recovery artifacts and escrow off-VM.

If capacity is unavailable, choose another eligible region or wait; never silently allocate a paid shape.
If reclaimed, preserve available disks/snapshots and rebuild a fresh qualified host through the supported
recovery procedure. Never admit competing old/new writers to one DB/bucket identity. Remove only explicitly
named deployment resources, retaining required archive custody and permanent deletion receipts.

[Oracle Always Free resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
checked 2026-10-18 documents reclaim risk. [Managed recovery differences](cloud-recovery.md).

## New in 0.12.0

See [the 0.12.0 settings](cloud-environment.md#new-settings-in-0120) and [choose your hosting](../choose-your-hosting.md). Oracle runs the host/full VPS shape, so everything in [choose your hosting](../choose-your-hosting.md) for the full VPS applies, including the photo clean-up model on the `card_models` volume and the control plane through an SSH tunnel.

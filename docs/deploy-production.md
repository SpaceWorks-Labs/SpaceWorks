# Production deployment

Choose [a hosting contract](deploy/cloud-overview.md) before provisioning. The choices are the existing supervised
VPS/Compose host, paid managed Redis or brokerless services, an additional opt-in best-effort free stack and Oracle
Always Free host/full. Verify actual provider prices/backup entitlements in the operator's account.

Use [managed setup](deploy/cloud-environment.md) for no-VPS deployment or [self-hosting](self-hosting.md) for a
supervised host. Runtime PostgreSQL requires direct/session transport; transaction poolers cannot retain required
advisory locks. Keep narrow runtime and finite maintenance credentials separate. Qualify S3 capabilities, sender
email and independently escrowed keys. Full managed needs web/worker/one scheduler; [free](deploy/cloud-free.md)
has a separate single-web/tick contract and never silently weakens a full installation.

[Recovery](deploy/cloud-recovery.md) distinguishes provider DB backup/PITR plus object durability, qualified
portable tenant dumps into fresh supervised targets and ordinary archive-and-purge records with no restore reader.
Managed host controls refuse server-side. Deploy through the provider; image rollback leaves forward migrations
applied. Check the release acceptance report before enabling traffic.

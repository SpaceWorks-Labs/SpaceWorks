"""Version vocabulary shared by compound producers and host capability installers."""


PROTOCOL_FAMILY = "spaceworks-lane-e-b1-v"
# v2 (P1b, owner decision #110): one platform-readable main component. v1 carried
# sovereign slices, reservation facts and a source-partition proof; no v1 archive
# without a sovereign slice could be built, so nothing produced under v1 is lost.
PROTOCOL_VERSION_NUMBER = 2
PROTOCOL_VERSION = f"{PROTOCOL_FAMILY}{PROTOCOL_VERSION_NUMBER}"

# A host may eventually consume several producer versions. First ship supports
# exactly one version, but records a real closed range so widening is explicit.
SUPPORTED_PROTOCOL_MINIMUM = PROTOCOL_VERSION
SUPPORTED_PROTOCOL_MAXIMUM = PROTOCOL_VERSION

"""Device Adapter API v1 (decisions 310-312): a vendor-neutral contract for bridges.

An adapter is an enrolled, signed device that manages many TARGETS (machine, machine type,
storage location, item, box, door, space) through bindings. What it may do is a set of
versioned CAPABILITIES held in ``registry``; each capability is one module under ``caps/``
with its JSON Schemas, so adding one means adding one module and listing it.
"""

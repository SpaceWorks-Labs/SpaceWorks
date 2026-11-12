"""Drop a stale cut-out when its holder's photo is replaced (decision 344(a)).

A cut-out made from an older photo can never print again (`cutouts.photo_variant_bytes` refuses it), but it kept its
private object and its storage charge until the next run. Every photo-replacing path calls this on commit, so the
derived object and its bytes go as soon as the new photo is saved. Lives beside `cutouts.py` (at its 300-line ceiling).
"""
from .cutouts import owner, purge_row, row_for


def purge_if_stale(kind, card):
    """After a photo replacement: delete the holder's cut-out when it was made from a different photo."""
    own = owner(kind, card)
    row = row_for(*own) if own else None
    if row is not None and row.source_key != (getattr(own[1], "photo_object_key", "") or ""):
        purge_row(row)

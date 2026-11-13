"""Resolve a historical borrower through the verified account-merge chain."""
from apps.accounts.models import User
from apps.accounts.staff_identity import actor_ids_for


def borrower_survivor(borrower):
    if borrower is None or borrower.pk is None:
        raise ValueError("Invalid borrower identity")
    current, seen = borrower.pk, set()
    for _ in range(33):
        if current in seen:
            raise ValueError("Cyclic borrower identity")
        seen.add(current)
        row = User._base_manager.filter(pk=current).values_list("pk", "merged_into_id").first()
        if row is None:
            raise ValueError("Missing borrower identity")
        if row[1] is None:
            aliases = actor_ids_for(User(pk=current))
            if borrower.pk not in aliases:
                raise ValueError("Invalid borrower alias chain")
            return User._base_manager.get(pk=current)
        current = row[1]
    raise ValueError("Borrower alias chain too deep")


def borrower_aliases(borrower):
    return actor_ids_for(borrower_survivor(borrower))

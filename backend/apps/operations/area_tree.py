"""One grouped-tree shape for the area views (decision 241).

Every grouped list (finance, To-Buy, consumables, repairs, warranties) is a tree of
groups: area first, then machine type and machine for machines, item category for
inventory, room or event where that is the natural owner. Each group carries its own
totals, summed from its leaves, so the console can show per-group totals and collapse
groups without adding anything up itself. A "none" group (`<kind>:none`, empty label)
holds rows not tied to one machine, type or category; the console words it.

The tree only arranges rows a source already scoped through rbac; it never widens reach.
"""

from decimal import Decimal
from apps.payments.money import trim_money

ITEM_CAP = 500
ZERO = Decimal("0.00")
FINANCE_COLUMNS = ("income", "other_income", "refunds", "expenses", "payouts", "owed")
PAYOUT_DERIVED = ("payouts", "money_out", "net")
CENT = Decimal("0.01")


def money_text(amount):
    """Money as a two-place string, three when a fils is present (KWD, BHD...)."""
    return None if amount is None else str(trim_money(amount))


class _Node:
    __slots__ = ("kind", "key", "label", "count", "attention", "money", "finance", "children", "items")

    def __init__(self, kind, key, label):
        self.kind, self.key, self.label = kind, key, label
        self.count = self.attention = 0
        self.money, self.finance, self.children, self.items = {}, {}, {}, []


def none_key(kind):
    return f"{kind}:none"


class GroupTree:
    """Add leaf rows under a path of `(kind, key, label)` steps; read back sorted groups."""

    def __init__(self, item_cap=ITEM_CAP):
        self.root = _Node("root", "", "")
        self.items_left = item_cap
        self.truncated = False

    def add(self, path, *, count=1, attention=0, money=None, finance=None, item=None):
        node, chain = self.root, [self.root]
        for kind, key, label in path:
            child = node.children.get(key)
            if child is None:
                child = node.children[key] = _Node(kind, key, label or "")
            node = child
            chain.append(node)
        for step in chain:
            step.count += count
            step.attention += attention
            for currency, amount in (money or {}).items():
                step.money[currency] = step.money.get(currency, ZERO) + amount
            for currency, columns in (finance or {}).items():
                totals = step.finance.setdefault(currency, dict.fromkeys(FINANCE_COLUMNS, ZERO))
                for column, amount in columns.items():
                    totals[column] += amount
        if item is not None:
            if self.items_left > 0:
                node.items.append(item)
                self.items_left -= 1
            else:
                self.truncated = True

    def groups(self, *, payouts=True):
        return [_dump(child, payouts) for child in _ordered(self.root)]

    def totals(self, *, payouts=True):
        return _dump(self.root, payouts)


def _ordered(node):
    # Named groups alphabetically; the "not tied to one ..." bucket always last.
    return sorted(node.children.values(), key=lambda child: (child.key.endswith(":none"), child.label.casefold(),
                                                              child.key))


def _finance_rows(finance, payouts):
    rows = []
    for currency in sorted(finance):
        values = finance[currency]
        money_in = values["income"] + values["other_income"]
        money_out = values["refunds"] + values["expenses"] + values["payouts"]
        row = {"currency": currency, **{key: money_text(value) for key, value in values.items()},
               "money_in": money_text(money_in), "money_out": money_text(money_out),
               "net": money_text(money_in - money_out)}
        if not payouts:
            # Payee money is session-only (#224c/#226g): the payout figure and every total
            # that includes it are dropped, not zeroed, so nothing is silently wrong.
            row = {key: value for key, value in row.items() if key not in PAYOUT_DERIVED}
        rows.append(row)
    return rows


def _dump(node, payouts):
    return {
        "kind": node.kind, "key": node.key, "label": node.label, "count": node.count,
        "attention": node.attention,
        "money": [{"currency": currency, "amount": money_text(node.money[currency])} for currency in sorted(node.money)],
        "finance": _finance_rows(node.finance, payouts),
        "children": [_dump(child, payouts) for child in _ordered(node)],
        "items": node.items,
    }

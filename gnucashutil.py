from __future__ import annotations

from gnucash import Account


def full_acc_name(acc: Account, maxdepth: int = 1000) -> str:
    if acc.parent is None or maxdepth == 0:
        return ""
    result = full_acc_name(acc.parent, maxdepth - 1)
    if result != "":
        result += ":"
    result += acc.name
    return result

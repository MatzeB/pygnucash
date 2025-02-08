#!/usr/bin/env python3
"""
Converts gnucash3 sqlite files to ledger format.
"""

from __future__ import annotations

import sys

import gnucash
from gnucash import Account, Commodity


def format_commodity(commodity: Commodity) -> str:
    mnemonic = commodity.mnemonic
    try:
        if mnemonic.encode("ascii").isalpha():
            return mnemonic
    except Exception:
        pass
    return f'"{mnemonic}"'  # TODO: escape " char in mnemonic


def full_acc_name(acc: Account) -> str:
    result = ""
    parent = acc.parent
    assert parent is not None
    parent_parent = parent.parent
    if parent_parent is not None:
        result = full_acc_name(parent) + ":"
    result += acc.name
    return result


def no_nl(string: str) -> str:
    return string.replace("\n", " ")


def _main() -> None:
    out = sys.stdout
    if len(sys.argv) == 1:
        sys.stderr.write(f"Invocation: {sys.argv[0]} gnucash_filename\n")
        sys.exit(1)
    data = gnucash.read_file(sys.argv[1])

    commodities = data.commodities.values()
    for commodity in commodities:
        if not commodity.mnemonic:
            continue
        out.write(f"commodity {format_commodity(commodity)}\n")
        if commodity.fullname:
            out.write(f"\tnote {no_nl(commodity.fullname)}\n")
    out.write("\n")

    accounts = list(data.accounts.values())
    accounts.sort(key=lambda acc: acc.guid)
    for acc in accounts:
        # ignore "dummy" accounts
        if acc.type is None or acc.type == "ROOT":
            continue
        if str(acc.commodity) == "template":
            continue
        out.write(f"account {full_acc_name(acc)}\n")
        if acc.description != "":
            out.write(f"\tnote {no_nl(acc.description)}\n")
        formated_commodity = format_commodity(acc.commodity)
        formated_commodity = formated_commodity.replace('"', '\\"')
        out.write(f'\tcheck commodity == "{formated_commodity}"\n')
        out.write("\n")

    # Prices
    prices = list(data.prices.values())
    prices.sort(key=lambda price: price.date)
    for price in prices:
        date = price.date.strftime("%Y/%m/%d %H:%M:%S")
        price_commodity = format_commodity(price.commodity)
        price_currency = format_commodity(price.currency)
        out.write(f"P {date} {price_commodity} {price.value} {price_currency}\n")
    out.write("\n")

    transactions = list(data.transactions.values())
    transactions.sort(key=lambda transaction: transaction.post_date)
    for trans in transactions:
        date = trans.post_date.strftime("%Y/%m/%d")
        code = f"({no_nl(trans.num.replace(')', ''))}) " if trans.num else ""
        description = no_nl(trans.description)
        out.write(f"{date} * {code}{description}\n")
        for split in trans.splits:
            # Ensure 2 spaces after account name
            out.write(f"\t{full_acc_name(split.account):<40s}  ")
            trans_currency = format_commodity(trans.currency)
            if split.account.commodity != trans.currency:
                commodity_precision = split.account.commodity.precision
                split_acc_commodity = format_commodity(split.account.commodity)
                quantity = split.quantity
                value = abs(split.value)
                out.write(
                    "%10.*f %s @@ %.2f %s"  # noqa: UP031
                    % (
                        commodity_precision,
                        quantity,
                        split_acc_commodity,
                        value,
                        trans_currency,
                    )
                )
            else:
                commodity_precision = trans.currency.precision
                out.write(
                    "%10.*f %s" % (commodity_precision, split.value, trans_currency)  # noqa: UP031
                )
            if split.memo:
                out.write(f"  ; {no_nl(split.memo)}")
            out.write("\n")
        out.write("\n")


if __name__ == "__main__":
    _main()

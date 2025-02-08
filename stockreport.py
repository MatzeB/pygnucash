#!/usr/bin/env python3
"""
Analysis tool for stock performance. Similar to the built-in advanced
portfolio view, but does a better job at figuring out fees, taxes and
dividends. Also computes lifetime wins/losses and yearly increase percentages
to ease comparisons between stocks that you hold for different durations of
time.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import TextIO

import gnucash
from gnucash import Account, Commodity, Transaction
from gnucashutil import full_acc_name


@dataclass(slots=True)
class Details:
    activa_changes: float = 0
    income: float = 0
    expenses: float = 0
    dividends: float = 0
    shares: float = 0
    shares_value: float = 0
    shares_moved: float = 0
    shares_moved_value: float = 0
    shares_other: float = 0
    shares_other_value: float = 0
    realized_gain: float = 0

    def verify(self) -> None:
        assert (
            abs(
                self.income
                + self.dividends
                + self.realized_gain
                - self.activa_changes
                - self.expenses
                - self.shares_value
                - self.shares_moved_value
                - self.shares_other_value
            )
            < 0.001
        )

    def __add__(self, other: object) -> Details:
        assert isinstance(other, Details)
        res = Details()
        keys = Details.__dataclass_fields__.keys()
        for key in keys:
            setattr(res, key, getattr(self, key) + getattr(other, key))
        res.verify()
        return res


def analyze_transaction(
    out: TextIO, acc: Account, transaction: Transaction
) -> tuple[Details, Commodity | None]:
    # Analyze the transaction splits.
    d = Details()
    other_commodity: Commodity | None = None
    for ssplit in transaction.splits:
        if ssplit.account == acc:
            d.shares += ssplit.quantity
            d.shares_value += ssplit.value
            continue

        acctype = ssplit.account.type
        if acctype == "EXPENSE":
            d.expenses += ssplit.value
        elif acctype in ("BANK", "ASSET", "EQUITY", "CREDIT"):
            d.activa_changes += ssplit.value
        elif acctype == "INCOME":
            d.income += -ssplit.value
        elif acctype in ("STOCK", "MUTUAL"):
            other_account = ssplit.account
            if other_account.commodity == acc.commodity:
                d.shares_moved += ssplit.quantity
                d.shares_moved_value += ssplit.value
            else:
                d.shares_other += ssplit.quantity
                d.shares_other_value += ssplit.value
                if other_commodity is None:
                    other_commodity = other_account.commodity
        else:
            date = transaction.post_date
            descr = transaction.description
            value = ssplit.value
            quant = ssplit.quantity
            out.write(f"Unexpected account type: {acctype} (acc {acc})\n")
            out.write(
                f"\t{date} {descr:<30}   value {value:.2f} quantity {quant:.2f}\n"
            )
            sys.exit(1)
    d.verify()
    return d, other_commodity


def categorize_transaction(analysis_details: Details) -> str | None:
    d = analysis_details
    if d.shares == 0 and d.shares_moved == 0 and d.shares_other == 0:
        # No change in share numbers at all, must be dividends or fees.
        if d.income > d.expenses:
            assert d.income > 0
            d.dividends += d.income
            d.income = 0
            return "DIV "  # dividends
        if d.expenses > d.income:
            assert d.expenses > 0
            return "FEE "  # account fee or borrowing fee
    elif d.shares_moved == 0 and d.shares_other == 0:
        if d.shares > 0 and (d.activa_changes < 0 or d.income > 0):
            return "BUY "
        if d.shares < 0 and d.activa_changes > 0:
            return "SELL"
        if d.shares > 0 and d.shares_other_value != 0:
            return "SPIN"  # spinoff (incoming)
        if d.shares_value == 0:
            return "SPLT" if d.shares > 0 else "MERG"
        if d.shares < 0 and d.expenses > 0:
            return "SELL"
    elif d.shares == 0 and d.shares_other > 0:
        return "SPIN"  # spinoff
    elif d.shares_moved != 0 and d.shares_moved == -d.shares:
        return "MOVE"  # securities moved to another account
    elif (d.shares < 0 and d.shares_other > 0) or (d.shares > 0 and d.shares_other < 0):
        return "CONV"  # "convert" (secutiry is renamed etc.)
    return None


@dataclass(slots=True, frozen=True)
class AccountAggregate:
    realized_gain: float
    shares_value: float
    expenses: float
    dividends: float
    shares: float
    realized_days: float
    period_begin: datetime | None


def analyze_account(out: TextIO, verbose: int, acc: Account) -> AccountAggregate:
    sum = Details()
    realized_days = 0.0
    period_begin: datetime | None = None

    splits = sorted(acc.splits, key=lambda x: x.transaction.post_date)
    processed_transactions = set()

    for split in splits:
        trans = split.transaction
        # stock splits can result in multiple splits in the same transaction
        # we only care about the transaction once
        if trans in processed_transactions:
            continue
        processed_transactions.add(trans)
        date = trans.post_date.strftime("%d.%m.%Y")
        curr = trans.currency

        # Analyze the transaction splits.
        d, other_commodity = analyze_transaction(out, acc, trans)
        tx_type = categorize_transaction(d)
        if tx_type is None:
            out.write("Error: Could not categorize transaction\n")
            out.write(f"{date} account {acc}\n")
            out.write(
                f"Activa Changes {d.activa_changes} "
                f"Income {d.income} "
                f"Expenses {d.expenses} "
                f"Shares {d.shares} (val {d.shares_value}) "
                f"Shares Moved {d.shares_moved} (val {d.shares_moved_value}) "
                f"Shares Other {d.shares_other} (val {d.shares_other_value})\n"
            )
            continue

        # Start a period when we moved from 0 to non-0 shares.
        sum.verify()
        d.verify()
        sum += d
        if d.shares != 0 and abs(sum.shares - d.shares) < 0.001:
            assert period_begin is None
            period_begin = trans.post_date
        if abs(sum.shares) < 0.001:
            # End a period when moving from non-0 to 0 shares.
            if d.shares != 0:
                period_end = trans.post_date
                assert period_begin is not None
                period_days = (period_end - period_begin).days
                realized_days += period_days
                period_begin = None
            sum.realized_gain += -sum.shares_value
            sum.shares_value = 0

        # Print transaction.
        if verbose >= 2:
            out.write(f"\t{date} {tx_type} ")
            if tx_type == "DIV ":
                out.write(f"{d.dividends:9.2f} {curr}, fees {d.expenses:7.2f}\n")
            elif tx_type == "FEE ":
                out.write(f"{d.activa_changes:0.2f} {curr}\n")
            else:
                out.write(
                    f"{-d.shares_value:9.2f} {curr}"
                    f", fees {d.expenses:7.2f}"
                    f", {d.shares:+5.1f} shares"
                )
                if d.shares != 0:
                    share_price = d.shares_value / d.shares
                    assert share_price >= 0
                    out.write(f" (@{share_price:3.2f})")
                out.write("\n")
            if tx_type in ("SPIN", "CONV") and other_commodity is not None:
                direction = "<-" if d.shares_other == 0 else "->"
                spin_shares = d.shares if d.shares_other == 0 else d.shares_other
                out.write(
                    f"\t {direction} {spin_shares:+7.f} shares {other_commodity}\n"
                )

    realized_gain = sum.realized_gain
    realized_gain += sum.dividends
    realized_gain -= sum.expenses
    return AccountAggregate(
        realized_gain=realized_gain,
        shares_value=sum.shares_value,
        expenses=sum.expenses,
        dividends=sum.dividends,
        shares=sum.shares,
        realized_days=realized_days,
        period_begin=period_begin,
    )


def get_latest_price(commodity: Commodity) -> tuple[float | None, datetime | None]:
    prices = commodity.prices
    if len(prices) == 0:
        return (None, None)
    return (prices[-1].value, prices[-1].date)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("gnucash_file")
    parser.add_argument("-v", "--verbose", action="count", default=0)
    args = parser.parse_args()

    data = gnucash.read_file(args.gnucash_file)

    out = sys.stdout
    verbose = args.verbose

    # Report
    gdividends = 0.0
    gexpenses = 0.0
    grealized_gain = 0.0
    gunrealized_gain = 0.0
    for acc in data.accounts.values():
        if acc.type != "STOCK" and acc.type != "MUTUAL":
            continue
        name = full_acc_name(acc, 3)
        if verbose >= 1:
            out.write(f"== {name} ({acc.commodity.mnemonic}) ==\n")

        aggregate = analyze_account(out, verbose, acc)
        realized_gain = aggregate.realized_gain
        shares_value = aggregate.shares_value
        expenses = aggregate.expenses
        dividends = aggregate.dividends
        shares = aggregate.shares

        if verbose >= 2:
            out.write("\t-------------\n")
        gexpenses += expenses
        gdividends += dividends

        if shares == 0.0:
            share_price: float = 0.0
            price_date: datetime | None = None
        else:
            share_price_n, price_date = get_latest_price(acc.commodity)
            assert share_price_n is not None
            assert price_date is not None
            share_price = share_price_n
        current_shares_value = shares * share_price
        unrealized_gain = current_shares_value - shares_value

        if verbose >= 1:
            out.write(
                f"\t{realized_gain:7.2f} realized gain incl. "
                f"{dividends:.2f} dividends, "
                f"{expenses:.2f} fees/tax\n"
            )
            if abs(unrealized_gain) > 0.001:
                price_suffix = ""
                if share_price != 0:
                    assert price_date is not None
                    date_string = price_date.strftime("%d.%m.%Y")
                    price_suffix = f" (@{share_price:.2f} on {date_string})"
                out.write(
                    f"\t{unrealized_gain:7.2f} unrealized: {shares:.0f} shares "
                    f"= {current_shares_value:5.2f}{price_suffix}\n"
                )
            out.write("\n")

        grealized_gain += realized_gain
        gunrealized_gain += unrealized_gain
    complete_gain = grealized_gain + gunrealized_gain
    out.write("-----------\n")
    out.write(f"{gexpenses:9.2f} Fees and Taxes\n")
    out.write(f"{gdividends:9.2f} Dividends\n")
    out.write(f"{grealized_gain:9.2f} gain realized\n")
    out.write(f"{gunrealized_gain:9.2f} gain unrealized\n")
    out.write("----\n")
    out.write(f"{complete_gain:9.2f} EUR complete gain\n")


if __name__ == "__main__":
    main()

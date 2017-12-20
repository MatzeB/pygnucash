#!/usr/bin/env python3
#
# Analysis tool for stock performance. Similar to the built-in advanced
# portfolio view, but does a better job at figuring out fees, taxes and
# dividens. Also computes lifetime wins/losses and yearly increase percentages
# to ease comparisons between stocks that you hold for different durations of
# time.
import gnucash
import math
import sys
import argparse
from gnucashutil import full_acc_name


class Details(object):
    _keys = ('activa_changes', 'income', 'expenses', 'dividends',
             'shares', 'shares_value', 'shares_moved',
             'shares_moved_value', 'shares_other', 'shares_other_value',
             'realized_gain')

    def __init__(self):
        for key in self._keys:
            setattr(self, key, 0)

    def verify(self):
        assert abs(self.income + self.dividends + self.realized_gain
                   - self.activa_changes - self.expenses - self.shares_value
                   - self.shares_moved_value - self.shares_other_value) < .001

    def __add__(self, other):
        res = Details()
        for key in self._keys:
            setattr(res, key, getattr(self, key) + getattr(other, key))
        res.verify()
        return res


def analyze_transaction(acc, transaction):
    # Analyze the transaction splits.
    d = Details()
    other_commodity = None
    for ssplit in transaction.splits:
        if ssplit.account == acc:
            d.shares += ssplit.quantity
            d.shares_value += ssplit.value
            continue

        acctype = ssplit.account.type
        if acctype == "EXPENSE":
            d.expenses += ssplit.value
        elif acctype in ("BANK", "ASSET", "EQUITY"):
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
            out.write("Unexpected account type: %s (acc %s)\n" %
                      (acctype, acc))
            out.write("\t%s %-30s   value %.2f quantity %.2f\n" %
                      (date, trans.description, ssplit.value,
                       ssplit.quantity))
            assert False
    d.verify()
    return d, other_commodity


def categorize_transaction(analysis_details):
    d = analysis_details
    if d.shares == 0 and d.shares_moved == 0 and d.shares_other == 0:
        # No change in share numbers at all, must be dividends or fees.
        if d.income > d.expenses:
            assert d.income > 0
            d.dividends += d.income
            d.income = 0
            return "DIV "  # dividends
        elif d.expenses > d.income:
            assert d.expenses > 0
            return "FEE "  # account fee or borrowing fee
        else:
            tx_type = None
    elif d.shares_moved == 0 and d.shares_other == 0:
        if d.shares > 0 and (d.activa_changes < 0 or d.income > 0):
            return "BUY "
        elif d.shares < 0 and d.activa_changes > 0:
            return "SELL"
        elif d.shares > 0 and d.shares_other_value != 0:
            return "SPIN"  # spinoff (incoming)
        elif d.shares_value == 0:
            return ("SPLT" if d.shares > 0 else "MERG")
    elif d.shares == 0 and d.shares_other > 0:
        return "SPIN"  # spinoff
    elif d.shares_moved != 0 and d.shares_moved == -d.shares:
        return "MOVE"  # securities moved to another account
    elif ((d.shares < 0 and d.shares_other > 0) or
          (d.shares > 0 and d.shares_other < 0)):
        return "CONV"  # "convert" (secutiry is renamed etc.)
    else:
        pass
    return None


def analyze_account(acc):
    sum = Details()
    realized_days = 0
    period_begin = None

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
        d, other_commodity = analyze_transaction(acc, trans)
        tx_type = categorize_transaction(d)
        if tx_type is None:
            out.write("Error: Could not categorize transaction\n")
            out.write("Activa Changes %s Income %s Expenses %s "
                      "Shares %s (val %s) Shares Moved %s (val %s) "
                      "Shares Other %s (val %s)\n" %
                      (d.activa_changes, d.income, d.expenses, d.shares,
                       d.shares_value, d.shares_moved, d.shares_moved_value,
                       d.shares_other, d.shares_other_value))
            continue

        # Start a period when we moved from 0 to non-0 shares.
        sum.verify()
        d.verify()
        sum += d
        if d.shares != 0 and abs(sum.shares - d.shares) < .001:
            assert period_begin is None
            period_begin = trans.post_date
        if abs(sum.shares) < .001:
            # End a period when moving from non-0 to 0 shares.
            if d.shares != 0:
                period_end = trans.post_date
                period_days = (period_end - period_begin).days
                realized_days += period_days
                period_begin = None
            sum.realized_gain += -sum.shares_value
            sum.shares_value = 0

        # Print transaction.
        if verbose >= 2:
            out.write("\t%s %s " % (date, tx_type))
            if tx_type == "DIV ":
                out.write("%9.2f %s, fees %7.2f\n" %
                          (d.dividends, curr, d.expenses))
            elif tx_type == "FEE ":
                out.write("%0.2f %s\n" %
                          (d.activa_changes, curr))
            else:
                out.write("%9.2f %s, fees %7.2f, %+5.1f shares" %
                          (-d.shares_value, curr, d.expenses, d.shares))
                if d.shares != 0:
                    share_price = d.shares_value / d.shares
                    assert share_price >= 0
                    out.write(" (@%3.2f)" % share_price)
                out.write("\n")
            if tx_type in ("SPIN", "CONV") and other_commodity is not None:
                direction = "<-" if d.shares_other == 0 else "->"
                spin_shares = (d.shares if d.shares_other == 0
                               else d.shares_other)
                out.write("\t %s %+7.f shares %s\n" %
                          (direction, spin_shares, other_commodity))

    realized_gain = sum.realized_gain
    realized_gain += sum.dividends
    realized_gain -= sum.expenses
    return (realized_gain, sum.shares_value, sum.expenses,
            sum.dividends, sum.shares, realized_days, period_begin)


def get_latest_price(commodity):
    prices = commodity.prices
    if len(prices) == 0:
        return (None, None)
    return (prices[-1].value, prices[-1].date)


def get_latest_share_value(acc, shares):
    commodity = acc.commodity
    prices = commodity.prices
    if len(prices) == 0:
        return float('NaN')
    last_price = prices[-1]
    value = shares * last_price.value
    return (value, last_price.value, last_price.date)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('gnucash_file')
    parser.add_argument('-v', '--verbose', action='count', default=0)
    args = parser.parse_args()

    data = gnucash.read_file(args.gnucash_file)

    global out
    out = sys.stdout
    global verbose
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
            out.write("== %s (%s) ==\n" % (name, acc.commodity.mnemonic))

        realized_gain, shares_value, expenses, dividends, shares, \
            realized_days, period_begin = analyze_account(acc)

        if verbose >= 2:
            out.write("\t-------------\n")
        gexpenses += expenses
        gdividends += dividends

        if shares == 0:
            share_price = 0
            price_date = None
        else:
            share_price, price_date = get_latest_price(acc.commodity)
        current_shares_value = shares * share_price
        unrealized_gain = current_shares_value - shares_value

        if verbose >= 1:
            out.write("\t%7.2f realized gain incl. %.2f dividends, "
                      "%.2f fees/tax\n" %
                      (realized_gain, dividends, expenses))
            if abs(unrealized_gain) > .001:
                price_suffix = ""
                if share_price != 0:
                    date_string = price_date.strftime("%d.%m.%Y")
                    price_suffix = (" (@%.2f on %s)" %
                                    (share_price, date_string))
                out.write("\t%7.2f unrealized: %.0f shares = %5.2f%s\n" %
                          (unrealized_gain, shares, current_shares_value,
                           price_suffix))
            out.write("\n")

        grealized_gain += realized_gain
        gunrealized_gain += unrealized_gain
    complete_gain = grealized_gain+gunrealized_gain
    out.write("-----------\n")
    out.write("%9.2f Fees and Taxes\n" % (gexpenses,))
    out.write("%9.2f Dividends\n" % (gdividends,))
    out.write("%9.2f gain realized\n" % (grealized_gain,))
    out.write("%9.2f gain unrealized\n" % (gunrealized_gain,))
    out.write("----\n")
    out.write("%9.2f EUR complete gain\n" % (complete_gain,))

if __name__ == "__main__":
    main()

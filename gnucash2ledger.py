#!/usr/bin/env python2
#
# Converts gnucash3 sqlite files to ledger format.
import sys
import codecs
import gnucash


def format_commodity(commodity):
    mnemonic = commodity.mnemonic
    try:
        if mnemonic.encode('ascii').isalpha():
            return mnemonic
    except:
        pass
    return "\"%s\"" % mnemonic   # TODO: escape " char in mnemonic


def full_acc_name(acc):
    result = ""
    if acc.parent.parent.parent is not None:
        result = full_acc_name(acc.parent) + ":"
    result += acc.name
    return result


def no_nl(string):
    return string.replace("\n", " ")


out = codecs.getwriter('UTF-8')(sys.stdout)
if len(sys.argv) == 1:
    sys.stderr.write("Invocation: %s gnucash_filename\n" % sys.argv[0])
    sys.exit(1)
data = gnucash.read_file(sys.argv[1])

commodities = data.commodities.values()
for commodity in commodities:
    if commodity.mnemonic == "":
        continue
    out.write("commodity %s\n" % format_commodity(commodity))
    if commodity.fullname != "":
        out.write("\tnote %s\n" % no_nl(commodity.fullname))
out.write("\n")

accounts = data.accounts.values()
for acc in accounts:
    # ignore "dummy" accounts
    if acc.type is None or acc.type == "ROOT":
        continue
    if str(acc.commodity) == "template":
        continue
    out.write("account %s\n" % (full_acc_name(acc), ))
    if acc.description != "":
        out.write("\tnote %s\n" % (no_nl(acc.description),))
    formated_commodity = format_commodity(acc.commodity)
    formated_commodity = formated_commodity.replace("\"", "\\\"")
    out.write("\tcheck commodity == \"%s\"\n" % formated_commodity)
    out.write("\n")

# Prices
prices = data.prices.values()
prices.sort(key=lambda x: x.date)
for price in prices:
    date = price.date.strftime("%Y/%m/%d %H:%M:%S")
    price_commodity = format_commodity(price.commodity)
    price_currency = format_commodity(price.currency)
    out.write("P %s %s %s %s\n" %
              (date, price_commodity, price.value, price_currency))
out.write("\n")

transactions = data.transactions.values()
transactions.sort(key=lambda x: x.post_date)
for trans in transactions:
    date = trans.post_date.strftime("%Y/%m/%d")
    code = "(%s) " % no_nl(trans.num.replace(")", "")) if trans.num else ""
    description = no_nl(trans.description)
    out.write("%s * %s%s\n" % (date, code, description))
    for split in trans.splits:
        # Ensure 2 spaces after account name
        out.write("\t%-40s  " % full_acc_name(split.account))
        trans_currency = format_commodity(trans.currency)
        if split.account.commodity != trans.currency:
            commodity_precision = split.account.commodity.precision
            split_acc_commodity = format_commodity(split.account.commodity)
            quantity = split.quantity
            value = abs(split.value)
            out.write("%10.*f %s @@ %.2f %s" %
                      (commodity_precision, quantity, split_acc_commodity, value, trans_currency))
        else:
            commodity_precision = trans.currency.precision
            out.write("%10.*f %s" % (commodity_precision, split.value, trans_currency))
        if split.memo:
            out.write("  ; %s" % no_nl(split.memo))
        out.write("\n")
    out.write("\n")

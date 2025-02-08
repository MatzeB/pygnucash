#!/usr/bin/env python
#
# Tool to change gnucash files. Currently this can move all transactions
# involving 1 account to another account.
import codecs
import gnucash
import sys
from gnucashutil import full_acc_name
from sys import stderr, exit

out = codecs.getwriter('UTF-8')(sys.stdout)
if len(sys.argv) < 3:
    stderr.write("Invocation: %s gnucash_filename COMMAND\n" % sys.argv[0])
    stderr.write("  Commands:\n")
    stderr.write("     accountlist         List account names+numbers\n")
    stderr.write("     switchacc old new   "
                 "Move all transactions from <old> to <new> account (specified as GUID)")
    exit(1)

conn = gnucash.open_file(sys.argv[1])
data = gnucash.read_data(conn)

if sys.argv[2] == "accountlist":
    for account in data.accounts.values():
        if account.type is None or account.type == "ROOT":
            continue
        if str(account.commodity) == "template":
            continue
        out.write("%s - %s\n" % (account.guid, full_acc_name(account, 3)))
elif sys.argv[2] == "switchacc":
    # TODO: Introduce some syntax to only select a subset of transactions
    # (or splits)

    # In a list of transactions switch account #1 to account #2
    fromguid = sys.argv[3]
    toguid = sys.argv[4]
    fromaccount = data.accounts.get(fromguid)
    toaccount = data.accounts.get(toguid)
    if fromaccount is None:
        stderr.write("There is no account '%s'" % fromguid)
        exit(1)
    if toaccount is None:
        stderr.write("There is no account '%s'" % toguid)
        exit(1)
    if fromaccount.commodity != toaccount.commodity:
        # TODO: maybe introduce an override switch, we could still do this if
        # the user really really wants it...
        stderr.write("Account commodities don't match up, this would go wrong")
        exit(1)

    for transaction in data.transactions.values():
        for split in transaction.splits:
            if split.account == fromaccount:
                stderr.write("Found split %s in transaction '%s'\n" %
                             (split.guid, transaction.description, ))
                gnucash.change_split_account(conn, split.guid,
                                             fromaccount.guid, toaccount.guid)
else:
    stderr.write("Unknown command %s\n" % sys.argv[2])

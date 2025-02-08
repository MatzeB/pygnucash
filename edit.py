#!/usr/bin/env python
"""
Tool to change gnucash files. Currently this can move all transactions
involving 1 account to another account.
"""

from __future__ import annotations

import codecs
import sys
from sys import exit, stderr

import gnucash
from gnucashutil import full_acc_name


def main() -> None:
    out = codecs.getwriter("UTF-8")(sys.stdout)
    if len(sys.argv) < 3:
        stderr.write(f"Invocation: {sys.argv[0]} gnucash_filename COMMAND\n")
        stderr.write("  Commands:\n")
        stderr.write("     accountlist         List account names+numbers\n")
        stderr.write(
            "     switchacc old new   "
            "Move all transactions from <old> to <new> account (specified as GUID)"
        )
        exit(1)

    conn = gnucash.open_file(sys.argv[1], writable=True)
    data = gnucash.read_data(conn)

    command = sys.argv[2]

    if command == "accountlist":
        for account in data.accounts.values():
            if account.type is None or account.type == "ROOT":
                continue
            if str(account.commodity) == "template":
                continue
            out.write(f"{account.guid} - {full_acc_name(account, 3)}\n")
    elif command == "switchacc":
        # TODO: Introduce some syntax to only select a subset of transactions
        # (or splits)

        # In a list of transactions switch account #1 to account #2
        fromguid = sys.argv[3]
        toguid = sys.argv[4]
        fromaccount = data.accounts.get(fromguid)
        toaccount = data.accounts.get(toguid)
        if fromaccount is None:
            stderr.write(f"There is no account '{fromguid}'")
            exit(1)
        if toaccount is None:
            stderr.write(f"There is no account '{toguid}'")
            exit(1)
        if fromaccount.commodity != toaccount.commodity:
            # TODO: maybe introduce an override switch, we could still do this if
            # the user really really wants it...
            stderr.write("Account commodities don't match up, this would go wrong")
            exit(1)

        for transaction in data.transactions.values():
            for split in transaction.splits:
                if split.account == fromaccount:
                    stderr.write(
                        f"Found split {split.guid} in transaction "
                        f"'{transaction.description}'\n"
                    )
                    gnucash.change_split_account(
                        conn, split.guid, fromaccount.guid, toaccount.guid
                    )
    else:
        stderr.write(f"Unknown command {command}\n")


if __name__ == "__main__":
    main()

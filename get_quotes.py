#!/usr/bin/env python3
"""
Download quotes from polygon.io. Expects an api-key in a `polygon_key.txt`
file in the current directory.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime

import requests

import gnucash
from gnucash import Commodity, GnuCashData, Price


@dataclass(slots=True, frozen=True)
class Data:
    close: float
    high: float
    low: float
    open: float
    time: datetime


def get_data_polygon(symbols: list[str]) -> dict[str, Data]:
    with open("polygon_key.txt", encoding="utf-8") as fp:
        auth_key = fp.read().strip()
    assert len(auth_key) == 32

    session = requests.Session()
    session.headers = {"Authorization": f"Bearer {auth_key}"}
    result: dict[str, Data] = {}
    base_url = "https://api.polygon.io"
    for symbol in symbols:
        url = f"{base_url}/v2/aggs/ticker/{symbol}/prev"
        response = session.get(url)
        if (
            not response.ok
            and "exceeded the maximum requests per minute" in response.text
        ):
            print("Throttling for request limits")
            time.sleep(60)
            response = session.get(url)
        if not response.ok:
            print(f"Request failed for {symbol}")
            print(response.text)
            sys.exit(1)
        data = json.loads(response.text)
        assert data["status"] == "OK"
        assert data["ticker"] == symbol
        if "results" not in data:
            print(f"No results for {symbol}")
            sys.exit(1)
        prices = data["results"][0]
        datum = Data(
            close=prices["c"],
            high=prices["h"],
            low=prices["l"],
            open=prices["o"],
            time=datetime.fromtimestamp(prices["t"] / 1000, tz=UTC),
        )
        result[symbol] = datum

    return result


def get_price_on_day(prices: list[Price], day: date) -> Price | None:
    for p in prices:
        if p.date.date() == day:
            return p
    return None


def get_latest_date(prices: list[Price]) -> date | None:
    latest: date | None = None
    for p in prices:
        if latest is None or p.date.date() > latest:
            latest = p.date.date()
    return latest


def get_currency(gnucashdata: GnuCashData, mnemonic: str) -> Commodity | None:
    for comm in gnucashdata.commodities.values():
        if comm.namespace == "CURRENCY" and comm.mnemonic == mnemonic:
            return comm
    return None


def main() -> None:
    if len(sys.argv) == 1:
        sys.stderr.write(f"Invocation: {sys.argv[0]} gnucash_filename\n")
        sys.exit(1)
    dbfile = sys.argv[1]
    gcconn = gnucash.open_file(dbfile, writable=True)
    gcdata = gnucash.read_data(gcconn)

    # Gather list of symbols that we want to fetch from yahoo.
    commodities = gcdata.commodities.values()
    comms = {}
    symbols = []
    for comm in commodities:
        if not comm.quote_flag:
            continue
        if comm.quote_source == "yahoo" or comm.quote_source == "yahoo_json":
            symbols.append(comm.mnemonic)
            assert comm.mnemonic not in comms  # hopefully have no duplicates
            comms[comm.mnemonic] = comm

    currency_usd = get_currency(gcdata, "USD")  # hardcoded for now
    assert currency_usd is not None

    if len(symbols) == 0:
        print("No commodities with quote_source == 'yahoo' found")
        sys.exit(0)

    for symbol in symbols:
        commodity = comms[symbol]
        latest = get_latest_date(commodity.prices)
        if latest is not None:
            delta = datetime.now(tz=UTC).date() - latest
            if delta.days <= 3:
                print(f"Data for {symbol} is new")
                continue

        print(f"Getting quotes for: {symbol}")
        sym_data = get_data_polygon([symbol])[symbol]
        price = sym_data.close
        time = sym_data.time
        day = sym_data.time.date()

        prev_data = get_price_on_day(commodity.prices, day)
        if prev_data is not None:
            print(f"{symbol}: Skipping (already have data for {day})")
        else:
            print(f"{symbol}: {price} on {day}")
            value_num = int(price * 10000)
            value_denom = 10000
            source = "Finance::Quote"  # Only some known strings accepted here
            gnucash.add_price(
                gcconn,
                commodity.guid,
                currency_usd.guid,
                time,
                source=source,
                type="last",
                value_num=value_num,
                value_denom=value_denom,
            )


if __name__ == "__main__":
    main()

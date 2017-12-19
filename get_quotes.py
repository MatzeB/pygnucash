#!/usr/bin/env python3
#
# Download quote from yahoo finance (for all STOCK commodities with
# quote_source set to yahoo).
import datetime
import gnucash
import requests
import sys


def get_yahoo_data(symbols):
    # Adapted from https://stackoverflow.com/a/47166822/1005674
    url = "https://query1.finance.yahoo.com/v7/finance/quote"
    fields = ['symbol', 'regularMarketPrice', 'regularMarketTime']
    payload = {
        'land': 'en-US',
        'region': 'US',
        'corsDomain': 'finance.yahoo.com',
        'fields': ','.join(fields),
        'symbols': ','.join(symbols),
    }
    r = requests.get(url, params=payload)
    return r.json()


def get_price_on_day(prices, day):
    for p in prices:
        if p.date.date() == day:
            return p
    return None


def get_currency(gnucashdata, mnemonic):
    for comm in gnucashdata.commodities.values():
        if comm.namespace == 'CURRENCY' and comm.mnemonic == mnemonic:
            return comm
    return None


def main():
    if len(sys.argv) == 1:
        sys.stderr.write("Invocation: %s gnucash_filename\n" % sys.argv[0])
        sys.exit(1)
    dbfile = sys.argv[1]
    gcconn = gnucash.open_file(dbfile)
    gcdata = gnucash.read_data(gcconn)

    # Gather list of symbols that we want to fetch from yahoo.
    commodities = gcdata.commodities.values()
    comms = dict()
    symbols = []
    for comm in commodities:
        if not comm.quote_flag or comm.quote_source != 'yahoo':
            continue
        symbols.append(comm.mnemonic)
        assert comm.mnemonic not in comms   # hopefully have no duplicates
        comms[comm.mnemonic] = comm

    currency_usd = get_currency(gcdata, 'USD')   # hardcoded for now

    if len(symbols) == 0:
        print("No commodities with quote_source == 'yahoo' found")
        sys.exit(0)

    print("Getting quotes for: %s" % ' '.join(symbols))
    yahoodata = get_yahoo_data(symbols)

    for sym in symbols:
        alldata = yahoodata['quoteResponse']['result']
        data = None
        for d in alldata:
            if d['symbol'] == sym:
                data = d
                break
        if data is None:
            print("Error: %s: No data" % sym)
            continue
        commodity = comms[sym]
        time = datetime.datetime.fromtimestamp(data['regularMarketTime'])
        day = time.date()

        prev_data = get_price_on_day(commodity.prices, day)
        if prev_data is not None:
            print("%s: Skipping (already have data for %s)" % (sym, day))
        else:
            print("%s: %s on %s" % (sym, data['regularMarketPrice'], day))
            # TODO: Actually insert data
            value_num = int(data['regularMarketPrice'] * 10000)
            value_denom = 10000
            source = 'Finance::Quote'  # Only some known strings accepted here
            gnucash.add_price(gcconn, commodity.guid, currency_usd.guid, time,
                              source=source, type='last',
                              value_num=value_num, value_denom=value_denom)


if __name__ == '__main__':
    main()

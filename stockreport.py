#!/usr/bin/env python
import sys
import codecs
import gnucash

out = codecs.getwriter('UTF-8')(sys.stdout)
if len(sys.argv) == 1:
	sys.stderr.write("Invocation: %s gnucash_filename\n" % sys.argv[0])
	sys.exit(1)
data = gnucash.read_file(sys.argv[1])

def full_acc_name(acc, maxdepth=1000):
	if acc.parent is None or maxdepth == 0:
		return ""
	result = full_acc_name(acc.parent, maxdepth-1)
	result += ":"+acc.name
	return result

# Calculate dividend amounts per account
def calc_dividends(acc):
	# Collect transactions involving currency and no number on this account
	sum_value = 0.0
	sum_fees = 0.0
	sum_dividends = 0.0
	count = 0
	for split in acc.splits:
		trans = split.transaction
		if split.quantity != 0:
			continue
		value = 0.0
		fees = 0.0
		dividends = 0.0
		for ssplit in trans.splits:
			if ssplit is split:
				continue
			acctype = ssplit.account.type
			if acctype == "EXPENSE":
				fees += abs(ssplit.value)
			elif acctype == "BANK":
				value += abs(ssplit.value)
			elif acctype == "INCOME":
				dividends += abs(ssplit.value)
			else:
				out.write("UNKNOWN TYPE: %s (acc %s)\n" % (acctype, acc))
				date = trans.post_date.strftime("%d.%m.%Y")
				out.write("\t%s %-30s   value %.2f quantity %.2f\n" %
						  (date, trans.description, ssplit.value, ssplit.quantity))
				assert False
		count += 1
		sum_value += value
		sum_fees += fees
		sum_dividends += dividends
		date = trans.post_date.strftime("%d.%m.%Y")
		out.write("\t%s DIV   %7.2f %s fees %7.2f\n" % (date, value, trans.currency, fees))
	
	assert abs(sum_value+sum_fees - sum_dividends) < .0001
	return (count, sum_value, sum_fees)

def calc_buy_sell(acc):
	sum_shares = 0
	sum_costs = 0.0
	sum_fees = 0.0
	for split in acc.splits:
		trans = split.transaction
		# quantity == 0 is probably a dividend, we don't care here
		shares = split.quantity
		if shares == 0:
			continue
		date = trans.post_date.strftime("%d.%m.%Y")
		curr = trans.currency
		is_buy = split.quantity > 0

		# Classify remaining splits into taxes+fees and real costs
		fees=0.0
		costs=0.0
		atype = "BUY " if is_buy else "SELL"
		for ssplit in trans.splits:
			if ssplit is split or ssplit.value == 0:
				continue
			acctype = ssplit.account.type
			if acctype == "EXPENSE":
				fees += abs(ssplit.value)
			elif acctype == "BANK" or acctype == "ASSET":
				costs += -ssplit.value
			elif acctype == "STOCK" or acctype == "MUTUAL":
				# moved to different depot? or a stock split?
				if ssplit.account == acc:
					# share split
					atype = "SPLT"
					shares += ssplit.quantity
				else:
					# moved to/from different depot, handle like a SELL
					assert costs == 0
					atype = "MIN " if is_buy else "MOUT"
					costs += -ssplit.value
			else:
				out.write("UNKNOWN TYPE: %s (acc %s)\n" % (acctype, acc))
				date = trans.post_date.strftime("%d.%m.%Y")
				out.write("\t%s %-30s   value %.2f quantity %.2f\n" %
						  (date, trans.description, ssplit.value, ssplit.quantity))
				assert False

		quantity = abs(split.quantity)
		out.write("\t%s %s %7s shares costs %9.2f %s fees %7.2f\n" % (
		          date, atype, quantity, abs(costs), curr, fees))
		sum_costs += costs
		sum_fees += fees
		sum_shares += split.quantity
	return (sum_costs, sum_fees, sum_shares)

def get_latest_share_value(acc, shares):
	commodity = acc.commodity
	prices = commodity.prices
	if len(prices) == 0:
		return float('NaN')
	last_price = prices[-1]
	value = shares * last_price.value
	return (value, last_price.date)

# Report
gdiv_value = 0.0
gdiv_fees = 0.0
gdiv_count = 0
grealized_gain = 0.0
gunrealized_gain = 0.0
gfees = 0.0
for acc in data.accounts.values():
	if acc.type != "STOCK" and acc.type != "MUTUAL":
		#out.write("IGNORE %s: %-40s\n" % (acc.type, full_acc_name(acc, 3)))
		continue
	name = full_acc_name(acc, 3)
	out.write("%-40s\n" % (name,))

	div_count, div_value, div_fees = calc_dividends(acc)
	acc.div_value = div_value
	acc.div_count = div_count
	acc.div_fees = div_fees
	gdiv_value += div_value
	gdiv_count += div_count
	gdiv_fees += div_fees
	
	costs, fees, shares = calc_buy_sell(acc)
	gfees += fees
	out.write("  => %5.0f shares, %9.2f costs %5.2f dividends %8.2f fees\n" % (shares, costs, acc.div_value, fees + acc.div_fees))
	if shares == 0:
		grealized_gain += -costs
	else:
		value, value_date = get_latest_share_value(acc, shares)
		date = value_date.strftime("%d.%m.%Y")
		out.write("  => share value %11.2f [on %s]\n" % (value, date))
		gunrealized_gain += -costs + value
out.write("-----------\n")
out.write("%9.2f fees\n" % (gdiv_fees+gfees,)) 
out.write("%9.2f EUR gain realized\n" % (grealized_gain,))
out.write("%9.2f EUR gain unrealized\n" % (gunrealized_gain,))
out.write("%9.2f EUR dividends\n" % (gdiv_value,))
out.write("----\n")
out.write("%9.2f EUR complete gain\n" % (grealized_gain+gunrealized_gain+gdiv_value))

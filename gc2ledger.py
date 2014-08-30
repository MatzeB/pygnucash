#!/usr/bin/env python
import sqlite3
import sys
import codecs
from datetime import datetime

out = codecs.getwriter('UTF-8')(sys.stdout)

class Account(object):
	def __init__(self):
		self.childs = []
		self.parent = None
		self.name = ""
		self.splits = []
		self.type = None
		self.dummy = True
	
	def __str__(self):
		return self.name

class Commodity(object):
	def __init__(self):
		self.fullname = ""
		self.namespace = ""
		self.dummy = True

	def __str__(self):
		return self.mnemonic

class Transaction(object):
	def __init__(self):
		self.dummy = True
		self.splits = []

class Split(object):
	def __init__(self):
		self.dummy = True

accounts = dict()
commodities = dict()
transactions = dict()
splits = dict()

def get(objdict, constructor, guid):
	acc = objdict.get(guid)
	if acc is None:
		acc = constructor()
		acc.guid = guid
		objdict[guid] = acc
	return acc

def get_account(guid):
	return get(accounts, Account, guid)

def get_commodity(guid):
	return get(commodities, Commodity, guid)

def get_transaction(guid):
	return get(transactions, Transaction, guid)

def get_split(guid):
	return get(splits, Split, guid)

# Read Data
conn = sqlite3.connect('test.db')
c = conn.cursor()

for row in c.execute('SELECT guid, namespace, mnemonic, fullname FROM commodities'):
	guid,namespace,mnemonic,fullname = row
	comm = get_commodity(guid)
	comm.namespace = namespace
	comm.mnemonic = mnemonic
	comm.fullname = fullname
	comm.dummy = comm.namespace == "template"

for row in c.execute('SELECT guid, name, account_type, commodity_guid, commodity_scu, non_std_scu, parent_guid, code, description FROM accounts'):
	guid,name,account_type,commodity_guid,commodity_scu,non_std_scu,parent_guid,code,description = row
	acc = get_account(guid)
	acc.name = name
	acc.parent = get_account(parent_guid)
	acc.parent.childs.append(acc)
	acc.description = description
	acc.commodity = get_commodity(commodity_guid)
	acc.type = account_type
	acc.dummy = acc.commodity.dummy

def parse_time(time):
	return datetime.strptime(time, "%Y%m%d%H%M%S")

for row in c.execute('SELECT guid, currency_guid, num, post_date, description FROM transactions'):
	guid,currency_guid,num,post_date,description = row
	trans = get_transaction(guid)
	trans.currency = get_commodity(currency_guid)
	trans.num = num
	trans.post_date = parse_time(post_date)
	trans.description = description
	trans.dummy = False

for row in c.execute('SELECT guid, tx_guid, account_guid, value_num, value_denom, quantity_num, quantity_denom FROM splits'):
	guid,tx_guid,account_guid,value_num,value_denom,quantity_num,quantity_denom = row
	split = get_split(guid)
	split.transaction = get_transaction(tx_guid)
	split.transaction.splits.append(split)
	split.account = get_account(account_guid)
	split.account.splits.append(split)
	split.value_num = int(value_num)
	split.value_denom = int(value_denom)
	split.value = float(value_num)/float(value_denom)
	split.quantity_num = int(quantity_num)
	split.quantity_denom = int(quantity_denom)
	split.quantity = float(quantity_num)/float(quantity_denom)

# Analysis

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

def calc_realized_wins(acc):
	for split in acc.splits:
		trans = split.transaction
		# quantity == 0 is probably a dividend, we don't care here
		if split.quantity == 0:
			continue
		date = trans.post_date.strftime("%d.%m.%Y")
		curr = trans.currency
		is_buy = split.quantity > 0

		# Classify remaining splits into taxes+fees and real costs
		fees=0.0
		costs=0.0
		atype = "BUY " if is_buy else "SELL"
		ignore_trans = False
		for ssplit in trans.splits:
			if ssplit is split or ssplit.value == 0:
				continue
			acctype = ssplit.account.type
			if acctype == "EXPENSE":
				fees += abs(ssplit.value)
			elif acctype == "BANK" or acctype == "ASSET":
				costs += abs(ssplit.value)
			elif acctype == "STOCK":
				# moved to different depot? or a stock split?
				if ssplit.account == acc:
					# probably a split, ignore
					ignore_trans = True
				else:
					# moved to/from different depot, handle like a SELL
					assert costs == 0
					atype = "MIN " if is_buy else "MOUT"
					costs += abs(ssplit.value)
			else:
				out.write("UNKNOWN TYPE: %s (acc %s)\n" % (acctype, acc))
				date = trans.post_date.strftime("%d.%m.%Y")
				out.write("\t%s %-30s   value %.2f quantity %.2f\n" %
						  (date, trans.description, ssplit.value, ssplit.quantity))
				assert False

		if ignore_trans:
			continue

		quantity = abs(split.quantity)
		out.write("\t%s %s %7s shares costs %9.2f %s fees %7.2f\n" % (
		          date, atype, quantity, costs, curr, fees))

# Report
gdiv_value = 0.0
gdiv_fees = 0.0
gdiv_count = 0
for acc in accounts.values():
	if acc.type != "STOCK":
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
	calc_realized_wins(acc)
	out.write("  => %5.2f dividends [%5.2f fees]\n" % (acc.div_value, acc.div_fees))
out.write("-----------\n")
out.write("%5.2f EUR dividens [%5.2f dividend fees]" % (gdiv_value, gdiv_fees))

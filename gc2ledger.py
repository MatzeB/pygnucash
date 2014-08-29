#!/usr/bin/env python
import sqlite3
import sys
from datetime import datetime

out = sys.stdout

conn = sqlite3.connect('test.db')

c = conn.cursor()
for row in c.execute('SELECT guid, currency_guid, num, post_date, enter_date, description FROM transactions'):
	#guid,currency_guid,post_data,enter_date,description = row
	pass

class Account(object):
	def __init__(self):
		self.childs = []
		self.parent = None
		self.name = ""
		self.splits = []
		self.dummy = True

class Commodity(object):
	def __init__(self):
		self.fullname = ""
		self.namespace = ""
		self.dummy = True

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
	split.value_num = value_num
	split.value_denom = value_denom
	split.quantity_num = quantity_num
	split.quantity_denom = quantity_denom

def full_acc_name(acc, maxdepth=1000):
	if acc.parent is None or maxdepth == 0:
		return ""
	result = full_acc_name(acc.parent, maxdepth-1)
	result += ":"+acc.name
	return result

#for acc in accounts.values():
#	if acc.name == "":
#		continue
#	name = full_acc_name(acc)
#	out.write("%s - %s (%s)\n" % (name, acc.description, acc.commodity.fullname))

# Select all stock accounts
stockaccounts = []
for acc in accounts.values():
	if acc.dummy or acc.commodity.namespace == "CURRENCY":
		continue
	stockaccounts.append(acc)
	name = full_acc_name(acc, 3)
	out.write("%-35s - %s (%s)\n" % (name, acc.description, acc.commodity.fullname))

class Transaction(object):
	def __init__(self):
		pass

from __future__ import annotations

import math
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from sqlite3 import Connection
from typing import TypeAlias, TypeVar

GUID: TypeAlias = str

_INVALID_DATETIME = datetime.max.replace(tzinfo=UTC)

_GuidObjT = TypeVar(
    "_GuidObjT", "Account", "Commodity", "Transaction", "Split", "Price"
)


def _guid_hash(self: _GuidObjT) -> int:
    return hash(self.guid)


def _guid_eq(self: _GuidObjT, other: object) -> bool:
    other_guid = getattr(other, "guid", None)
    assert isinstance(other_guid, str)
    return self.guid == other_guid


@dataclass(slots=True)
class Account:
    guid: str
    name: str = ""
    parent: Account | None = None
    childs: list[Account] = field(default_factory=list)
    description: str = ""
    _commodity: Commodity | None = None
    splits: list[Split] = field(default_factory=list)
    type: str = ""

    @property
    def commodity(self) -> Commodity:
        commodity = self._commodity
        assert commodity is not None
        return commodity

    def __str__(self) -> str:
        return self.name

    __hash__ = _guid_hash
    __eq__ = _guid_eq


@dataclass(slots=True)
class Commodity:
    guid: str
    fullname: str = ""
    mnemonic: str = ""
    namespace: str = ""
    precision: int = 2
    quote_flag: bool = False
    quote_source: str = ""
    prices: list[Price] = field(default_factory=list)

    def __str__(self) -> str:
        return self.mnemonic

    __hash__ = _guid_hash
    __eq__ = _guid_eq


@dataclass(slots=True)
class Transaction:
    guid: str
    _currency: Commodity | None = None
    num: str = ""
    post_date: datetime = _INVALID_DATETIME
    description: str = ""
    splits: list[Split] = field(default_factory=list)

    @property
    def currency(self) -> Commodity:
        currency = self._currency
        assert currency is not None
        return currency

    __hash__ = _guid_hash
    __eq__ = _guid_eq


@dataclass(slots=True)
class Split:
    guid: str
    _transaction: Transaction | None = None
    _account: Account | None = None
    value_num: int = 0
    value_denom: int = 0
    value: float = float("nan")
    quantity_num: int = 0
    quantity_denom: int = 0
    quantity: float = float("nan")
    memo: str = ""

    @property
    def transaction(self) -> Transaction:
        transaction = self._transaction
        assert transaction is not None
        return transaction

    @property
    def account(self) -> Account:
        account = self._account
        assert account is not None
        return account

    __hash__ = _guid_hash
    __eq__ = _guid_eq


@dataclass(slots=True)
class Price:
    guid: str
    _commodity: Commodity | None = None
    _currency: Commodity | None = None
    date: datetime = _INVALID_DATETIME
    value_num: int = 0
    value_denom: int = 0
    value: float = float("nan")

    @property
    def commodity(self) -> Commodity:
        commodity = self._commodity
        assert commodity is not None
        return commodity

    @property
    def currency(self) -> Commodity:
        currency = self._currency
        assert currency is not None
        return currency

    __hash__ = _guid_hash
    __eq__ = _guid_eq


@dataclass(slots=True)
class GnuCashData:
    accounts: dict[GUID, Account] = field(default_factory=dict)
    commodities: dict[GUID, Commodity] = field(default_factory=dict)
    transactions: dict[GUID, Transaction] = field(default_factory=dict)
    splits: dict[GUID, Split] = field(default_factory=dict)
    prices: dict[GUID, Price] = field(default_factory=dict)


def _get_data_cached(
    objdict: dict[GUID, _GuidObjT], constructor: type[_GuidObjT], guid: GUID
) -> _GuidObjT:
    assert isinstance(guid, GUID)
    obj = objdict.get(guid)
    if obj is None:
        obj = constructor(guid=guid)
        objdict[guid] = obj
    return obj


def get_account(data: GnuCashData, guid: GUID) -> Account:
    return _get_data_cached(data.accounts, Account, guid)


def get_commodity(data: GnuCashData, guid: GUID) -> Commodity:
    return _get_data_cached(data.commodities, Commodity, guid)


def get_transaction(data: GnuCashData, guid: GUID) -> Transaction:
    return _get_data_cached(data.transactions, Transaction, guid)


def get_split(data: GnuCashData, guid: GUID) -> Split:
    return _get_data_cached(data.splits, Split, guid)


def get_price(data: GnuCashData, guid: GUID) -> Price:
    return _get_data_cached(data.prices, Price, guid)


def open_file(filename: str, writable: bool = False) -> Connection:
    if writable:
        return sqlite3.connect(filename)
    return sqlite3.connect(f"file:{filename}?mode=ro", uri=True)


def _parse_time(time_str: str) -> datetime:
    try:
        # try gnucash 3 format
        return datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
    except ValueError:
        return datetime.strptime(time_str, "%Y%m%d%H%M%S").replace(tzinfo=UTC)


def read_data(connection: Connection) -> GnuCashData:
    c = connection.cursor()

    data = GnuCashData()
    for row in c.execute(
        "SELECT guid, namespace, mnemonic, fullname, "
        "fraction, quote_flag, quote_source "
        "FROM commodities"
    ):
        guid, namespace, mnemonic, fullname, fraction, quote_flag, quote_source = row
        comm = get_commodity(data, guid)
        comm.namespace = namespace
        comm.mnemonic = mnemonic
        comm.fullname = fullname
        comm.quote_flag = quote_flag != 0
        comm.quote_source = quote_source
        comm.precision = int(math.log10(fraction))

    for row in c.execute(
        "SELECT guid, name, account_type, commodity_guid, "
        "commodity_scu, non_std_scu, parent_guid, code, "
        "description FROM accounts"
    ):
        (
            guid,
            name,
            account_type,
            commodity_guid,
            _commodity_scu,
            _non_std_scu,
            parent_guid,
            _code,
            description,
        ) = row
        if commodity_guid:
            commodity = get_commodity(data, commodity_guid)
        else:
            commodity = None
        if parent_guid:
            parent = get_account(data, parent_guid)
        else:
            parent = None
        acc = get_account(data, guid)
        acc.name = name
        acc.parent = parent
        acc.description = description
        acc._commodity = commodity
        acc.type = account_type
        if parent is not None:
            parent.childs.append(acc)

    for row in c.execute(
        "SELECT guid, currency_guid, num, post_date, description FROM transactions"
    ):
        guid, currency_guid, num, post_date, description = row
        trans = get_transaction(data, guid)
        trans._currency = get_commodity(data, currency_guid)
        trans.num = num
        trans.post_date = _parse_time(post_date)
        trans.description = description

    for row in c.execute(
        "SELECT guid, tx_guid, account_guid, memo, "
        "value_num, value_denom, quantity_num, "
        "quantity_denom FROM splits"
    ):
        (
            guid,
            tx_guid,
            account_guid,
            memo,
            value_num,
            value_denom,
            quantity_num,
            quantity_denom,
        ) = row
        split = get_split(data, guid)
        split._transaction = get_transaction(data, tx_guid)
        split._transaction.splits.append(split)
        split._account = get_account(data, account_guid)
        split._account.splits.append(split)
        split.value_num = int(value_num)
        split.value_denom = int(value_denom)
        split.value = float(value_num) / float(value_denom)
        split.quantity_num = int(quantity_num)
        split.quantity_denom = int(quantity_denom)
        split.quantity = float(quantity_num) / float(quantity_denom)
        split.memo = memo

    for row in c.execute(
        "SELECT guid, commodity_guid, currency_guid, date, "
        "value_num, value_denom FROM prices"
    ):
        guid, commodity_guid, currency_guid, date, value_num, value_denom = row
        price = get_price(data, guid)
        price._commodity = get_commodity(data, commodity_guid)
        price._commodity.prices.append(price)
        price._currency = get_commodity(data, currency_guid)
        price.date = _parse_time(date)
        price.value_num = int(value_num)
        price.value_denom = int(value_denom)
        if int(value_denom) == 0:
            price.value = 0.0
        else:
            price.value = float(value_num) / float(value_denom)

    # Sort price lists for each commodity
    for commodity in data.commodities.values():
        prices = commodity.prices
        prices.sort(key=lambda price: price.date)

    return data


def read_file(filename: str) -> GnuCashData:
    with open_file(filename) as conn:
        return read_data(conn)


# Functions to change data


def change_split_account(
    connection: Connection,
    split_guid: GUID,
    oldaccount_guid: GUID,
    newaccount_guid: GUID,
) -> None:
    connection.execute(
        "UPDATE splits SET account_guid=? WHERE guid=? AND account_guid=?",
        (newaccount_guid, split_guid, oldaccount_guid),
    )
    connection.commit()


def _print_time(time: datetime) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def add_price(
    connection: Connection,
    commodity_guid: GUID,
    currency_guid: GUID,
    date: datetime,
    source: GUID,
    type: str,
    value_num: int,
    value_denom: int,
) -> GUID:
    guid = uuid.uuid4().hex
    date_f = _print_time(date)
    connection.execute(
        "INSERT INTO prices(guid, commodity_guid, "
        "currency_guid, date, source, type, value_num, "
        "value_denom) VALUES (?,?,?,?,?,?,?,?)",
        (
            guid,
            commodity_guid,
            currency_guid,
            date_f,
            source,
            type,
            value_num,
            value_denom,
        ),
    )
    connection.commit()
    return guid

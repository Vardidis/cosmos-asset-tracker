from django.db import models

class Asset1:
    symbol: str
    identifier: str
    pos_price: float
    cur_price: float
    pos_amount: float
    change_perc: float
    change_abs: float
    svg: str

class Asset2:
    symbol: str
    price: float
    svg: str
    delegate_amount: float
    balance: float
    unbonding_amount: float
    rewards_amount: float

class StatLoader:
    svg: str
    total_balance: float
    allocated_balance_denoms: str
    allocated_balance: float
    allocated_balance_index: int
    validators: str
    delegate_shares: float
    total_delegated: float

class Transaction:
    action: str
    amount: float
    fees: float
    hash: str
    date: str
    receiver: bool

class AssetSerialized:
    symbol: str
    amount: float
    address: str
    rewards: float
    init_amount: float
    fees: float
    txs: int
    pages: int
    final_amount: float
    failed: int
    updated: int
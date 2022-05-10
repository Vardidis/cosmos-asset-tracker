from django.db import models

class Asset():
    symbol: str
    price: float

    def __init__(self, symbol, price):
        self.symbol = symbol
        self.price = price

    def __str__(self):
        return self.symbol

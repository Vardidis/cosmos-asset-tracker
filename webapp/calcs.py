from flask import session
import requests
import json
from datetime import datetime
import pymongo
import os
from .models import *

uri = os.environ.get('MONGO_URI', 'mongodb+srv://fivosvardis:123.456.789@cluster0.74bck.mongodb.net/myFirstDatabase?retryWrites=true&w=majority')

def fetch_cur_price(asset:str, currency:str='usd') -> float:
    ans = requests.get('https://api.coingecko.com/api/v3/simple/price?ids=' + asset.lower() + '&vs_currencies=' + currency)
    if(json.loads(ans.content)[asset] != {}):
        return json.loads(ans.content)[asset][currency]
    else:
        return 0


def change_percent(open_price:float, close_price:float) -> float:
    return float('{:.2f}'.format((close_price - open_price) / open_price * 100))

def get_time() -> str:
    timeVar = datetime.now().strftime('%H:%M')
    return timeVar

def total(listing:dict[Asset1]) -> float:
    sum = 0
    for i in listing:
        aux = i.cur_price * i.pos_amount
        sum += aux
    return sum

def insert_asset() -> int:
    client = pymongo.MongoClient(uri)
    db = client['asset_tracker']
    collection = db['assets']
    collection3 = db['unverified']

    asset = Asset1()
    res = collection.find({})
    n = 0
    flag = False
    for i in res:
        n += 1
        if(asset.symbol == i['symbol']):
            asset.identifier = i['identifier']
            asset.svg = i['svg']
            if(i['pos_amount'] == 0):
                collection.update_one({'_id': i['_id'], '$set': {
                                'pos_price': asset.pos_price,
                                'pos_amount': asset.pos_amount
                                }})
            else:
                m = 1
                for j in i['extra']:
                    m += 1
                collection.update_one({'_id': i['_id'], '$set': {'extra': {str(m): asset.pos_price, str(0-m): asset.pos_amount}}})
            flag = True
            break
    if(not flag):
        collection3.insert_one({'_id': n,
                                'symbol': asset.symbol,
                                'pos_price': asset.pos_price,
                                'pos_amount': asset.pos_amount,
                                'identifier': '',
                                'svg': ''})
        return 1
    return 0



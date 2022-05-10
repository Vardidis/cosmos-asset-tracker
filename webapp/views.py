from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.http import HttpResponse
from multiprocessing import Pool
from .models import *
from . import calcs
import pymongo
import os
import json
import requests
from .Asset import *
import time

uri = os.environ.get('MONGO_URI', '')
p = None

def home(request):
    client = pymongo.MongoClient(uri)
    db = client['asset_tracker']
    collection = db['assets']
    collection3 = db['unverified']
    res = collection.find({})

    # asset = Asset()
    # asset.symbol = request.POST['asset']
    # asset.pos_price = float(request.POST['price'])
    # asset.pos_amount = float(request.POST['amount'])
    n = 0
    flag = False
    # for i in res:
    #     n += 1
    #     asset.identifier = i['identifier']
    #     asset.svg = i['svg']
    #     if(i['pos_amount'] == 0):
    #         collection.update_one({'_id': i['_id'], '$set': {
    #                         'pos_price': asset.pos_price,
    #                         'pos_amount': asset.pos_amount
    #                         }})
    #     else:
    #         if(i['extra']):
    #             m = 1
    #             for j in i['extra']:
    #                 m += 1
    #             collection.update_one({'_id': i['_id'], '$set': {'extra': {str(m): asset.pos_price, str(0-m): asset.pos_amount}}})
    #     flag = True
    #     break
    # n = 0

    listing = []
    sum = 0
    res = collection.find({})
    for i in res:
        if(i['pos_amount'] > 0):
            asset = Asset1()
            asset.symbol = i['symbol']
            asset.pos_price = i['pos_price']
            asset.pos_amount = i['pos_amount']
            asset.cur_price = calcs.fetch_cur_price(i['identifier'])
            asset.svg = i['svg']
            asset.change_perc = calcs.change_percent(asset.pos_price, asset.cur_price)
            asset.change_abs = float('{:.2f}'.format(asset.cur_price * asset.pos_amount - asset.pos_price * asset.pos_amount))
            listing.append(asset)
            sum += asset.change_abs
            test = []
            try:
                clicked = request.GET['clicked']
            except:
                clicked = False
            if(clicked):
                symbol = request.GET['symbol']
                wallet = request.GET['address']                
                for i,j in wallet:
                    res = collection.find_one({'symbol': symbol})
                    if(res['chain'] == i):
                        address = j
                sL = StatLoader()
                sL.delegate_amount = json.loads(requests.get(i['endpoints']['delegate'].replace('<ADDRESS>', address)).content)['result']['balance']['amount']
                test.append(sL)
    sum = float('{:.2f}'.format(sum))
    total = float('{:.2f}'.format(calcs.total(listing)))




    return render(request, 'home.html', {'assets': listing, 'sum': sum, 'total': total, 'test': test})
    

def stats(request):
    client = pymongo.MongoClient(uri)
    db = client['asset_tracker']
    collection = db['staging']
    res = collection.find({})

    n = 0
    flag = False

    listing = []
    sum = 0
    res = collection.find({})
    for i in res:
        asset = Asset2()
        asset.symbol = i['symbol']
        asset.cur_price = json.loads(requests.get(i['endpoints']['price']).content)[i['name']]['usd']
        asset.svg = i['svg']
        #asset.delegate_amount = json.loads(requests.get(i['endpoints']['delegate']).content)['result']['balance']['amount']
        # asset.change_perc = calcs.change_percent(asset.pos_price, asset.cur_price)
        # asset.change_abs = float('{:.2f}'.format(asset.cur_price * asset.pos_amount - asset.pos_price * asset.pos_amount))
        listing.append(asset)
            # sum += asset.change_abs
    # sum = float('{:.2f}'.format(sum))
    # total = float('{:.2f}'.format(calcs.total(listing)))
    total = 0
    return render(request, 'stats.html', {'assets': listing, 'sum': sum, 'total': total})

def getBalance(request, address):
    ans = requests.get("https://lcd-sentinel.keplr.app/bank/balances/" + address)
    return HttpResponse(json.loads(ans.content)['result'][0]['amount'])

def getData(request):
    client = pymongo.MongoClient(uri)
    db = client['asset_tracker']
    collection = db['staging']

    res = collection.find({})
    aux = []

    sL = StatLoader()
    symbol = request.GET['symbol']
    addr = request.GET['address']
    sL.total_balance = 0
    sL.allocated_balance_denoms = []
    sL.allocated_balance = []
    sL.validators = []
    sL.delegate_shares = []
    sL.total_delegated = 0
    for i in res:
        if(i['symbol'] == symbol):
            sL.svg = i['svg']
            response = json.loads(requests.get(i['api'] + i['endpoints']['balance'].replace('<ADDRESS>', addr)).content)['result']
            if(response != []):
                for j in response:
                    if(j['denom'] == 'u' + i['symbol'].lower()):
                        sL.total_balance = float(j['amount']) / 1000000
                    else:
                        sL.allocated_balance_denoms.append(j['denom'])
                        sL.allocated_balance.append(float(j['amount']) / 1000000)
            
            response = json.loads(requests.get(i['api'] + i['endpoints']['delegate'].replace('<ADDRESS>', addr)).content)['result']
            if(response != []):
                for j in response:
                    if(j['delegation']):
                        sL.validators.append(j['delegation']['validator_address'])
                        sL.delegate_shares.append(float(j['delegation']['shares']) / 1000000)
                    if(j['balance']):
                        sL.total_delegated = float(j['balance']['amount']) / 1000000
            break
    aux.append({'svg': sL.svg, 'total_balance': sL.total_balance, 'allocated_balance': sL.allocated_balance, 'allocated_balance_denoms': sL.allocated_balance_denoms, 'validators': sL.validators, 'total_delegated': sL.total_delegated, 'delegate_shares': sL.delegate_shares})
            
    return HttpResponse(json.dumps(aux[0]))


def master(request):
    return render(request, 'master.html')



def dev(request):
    client = pymongo.MongoClient(uri)
    db = client['asset_tracker']
    collection = db['assets']
    res = collection.find({})

    n = 0
    flag = False

    listing = []
    sum = 0
    res = collection.find({})
    for i in res:
        if(i['pos_amount'] > 0):
            asset = Asset1()
            asset.symbol = i['symbol']
            asset.pos_price = i['pos_price']
            asset.pos_amount = i['pos_amount']
            asset.cur_price = calcs.fetch_cur_price(i['identifier'])
            asset.svg = i['svg']
            asset.change_perc = calcs.change_percent(asset.pos_price, asset.cur_price)
            asset.change_abs = float('{:.2f}'.format(asset.cur_price * asset.pos_amount - asset.pos_price * asset.pos_amount))
            listing.append(asset)
            sum += asset.change_abs
            test = []
            try:
                clicked = request.GET['clicked']
            except:
                clicked = False
            if(clicked):
                symbol = request.GET['symbol']
                wallet = request.GET['address']                
                for i,j in wallet:
                    res = collection.find_one({'symbol': symbol})
                    if(res['chain'] == i):
                        address = j
                sL = StatLoader()
                sL.delegate_amount = json.loads(requests.get(i['endpoints']['delegate'].replace('<ADDRESS>', address)).content)['result']['balance']['amount']
                test.append(sL)
    sum = float('{:.2f}'.format(sum))
    total = float('{:.2f}'.format(calcs.total(listing)))




    return render(request, 'devHome.html', {'assets': listing, 'sum': sum, 'total': total, 'test': test})


def juno(request):
    
    return render(request, 'juno.html')#, {'symbol': asset.symbol, 'init': asset.init_amount, 'final': asset.final_amount, 'total': asset.init_amount - asset.final_amount, 'amount': asset.amount, 'rewards': asset.rewards, 'txs': asset.txs, 'fees': asset.fees, 'failed': asset.failed, 'updated': asset.updated})


def get_all_txs(request):
    #   TODO
    #   FIGURE OUT THE PURPOSE OF EXTRA DETAILS;
    
    #   TESTED
    #   TXS SHOW THE EXACT AMOUNT --TESTED;
    #   DELEGATIONS ARE PRECISE -- TESTED;
    #   PROPOSALS ARE OK -- TESTED;
    #   UNBONDING IS OK -- TESTED;
    #   REWARDS RE OK -- TESTED;
    #   IMPORT MORE ASSETS TO MONGODB

    symbol = request.GET['asset']
    address = request.GET['address']
    aux = []

    if(symbol == 'ATOM'):
        obj = Atom(symbol, address, uri)
    elif(symbol == 'JUNO'):
        obj = Juno(symbol, address, uri)
    elif(symbol == 'OSMO'):
        obj = Osmo(symbol, address, uri)
        
    obj.fetch_txs()
    obj.get_balance()    
    aux.append({'symbol': obj.symbol, 'amount': float('{:.6f}'.format(obj.balance)), 'rewards': float('{:.6f}'.format(obj.rewards)), 'txs': obj.txs, 'fees': float('{:.6f}'.format(obj.fees)), 'failed': obj.failed, 'delegated': float('{:.6f}'.format(obj.delegated)), 'unbonding': float('{:.6f}'.format(obj.unbonding)), 'proposals': obj.proposals, 'votes': obj.votes}) #'test': asset.test})

    try:
        return JsonResponse(aux[0], safe=False)
    except:
        return JsonResponse([], safe=False)
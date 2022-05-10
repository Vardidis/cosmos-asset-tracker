from http.client import FAILED_DEPENDENCY
import requests
import json
import pymongo
from datetime import timezone, datetime
import time

class Asset:
    '''
        Representation of summary of data from all the batches of transactions.
        Each crypto self is represented by an self object to assist calculation of its attributes.
        self objects are then serialized into self models in order to get passed on the front-end.
    '''

    def __init__(self, symbol:str, address:str, mongo_uri:str) -> None:
        self.symbol = symbol
        self.address = address
        self.amount = self.init_amount = self.rewards = self.fees = self.unbonding = self.delegated = 0.0
        self.pages = self.txs = self.offset = self.failed = self.proposals = 0
        self.votes = []
        client = pymongo.MongoClient(mongo_uri)
        db = client['asset_tracker']
        self.collection = db['staging']
        

    def fetch_txs(self) -> list[dict]:
        flag = True
        offset = 0

        res = self.collection.find_one({'symbol': self.symbol})
        api = res['endpoints']['mint_name']

        while(flag):
            url = 'https://<API>.cosmostation.io/v1/account/new_txs/<ADDRESS>?limit=50&from=<FLOOR>'.replace('<FLOOR>', str(offset)).replace('<ADDRESS>', self.address).replace('<API>', api)
            ans = json.loads(requests.get(url).content)

            try:
                assert (ans != [])
            except AssertionError:
                continue

            self.pages += 1
            flag = not (len(ans) < 50)

            offset = ans[-1]['header']['id']

            self.iterate_txs(ans)      
        
        self.final_amount = self.amount * self.get_price()
            
    def get_fees(self, tx) -> float:
        try:
            return float(tx['data']['tx']['auth_info']['fee']['amount'][0]['amount']) / 1000000
        except IndexError:
            return 0.0

    def get_amount(self, tx:dict) -> float:
        try:
            ans = float(tx['data']['tx']['body']['messages'][0]['token']['amount']) / 1000000
        except KeyError:
            try:
                ans = float(tx['data']['tx']['body']['messages'][0]['amount'][0]['amount']) / 1000000
            except KeyError:
                ans = float(tx['data']['tx']['body']['messages'][0]['amount']['amount']) / 1000000
        except:
            ans = 0
        finally:
            return ans

    def get_metadata(self, tx:dict) -> str:
        return tx['header']['timestamp'].replace('Z', '').replace('T', ' ')
        
    def is_receiver(self, tx:dict) -> bool:
        for i in tx['data']['logs'][0]['events']:
            for j in i['attributes']:
                if(j['key'] == 'receiver'):
                    return j['value'] == self.address

    def get_action(self, tx:dict) -> str or list[str]:

    #   TODO
    #   RE-DESIGN TO HANDLE MULTIPLE LOG EVENTS (PROBABLY ADD BETTER VALIDATION SYSTEM);

        if(len(tx['data']['logs']) == 1):
            events = tx['data']['logs'][0]['events']
            for index in events:
                if(index['type'] == 'message'):
                    for option in index['attributes']:
                        if(option['key'] == 'action'):
                            action = option['value']
                            if(action == '/cosmos.gov.v1beta1.MsgVote'):
                                return 'proposal'
                            elif(action == '/cosmos.bank.v1beta1.MsgSend'):
                                return 'transfer'
                            elif(action == '/cosmos.distribution.v1beta1.MsgWithdrawDelegatorReward'):
                                return 'reward'
                            elif(action == '/cosmos.staking.v1beta1.MsgDelegate'):
                                return 'delegate'
                            elif(action == '/cosmos.staking.v1beta1.MsgUndelegate'):
                                return 'undelegate'
                            elif(action == '/ibc.applications.transfer.v1.MsgTransfer'):
                                return 'ibc_transfer'
                            elif(action == '/ibc.core.client.v1.MsgUpdateClient'):
                                continue
                            elif(action == '/osmosis.gamm.v1beta1.MsgSwapExactAmountIn'):
                                return 'lp_swap'
                            elif(action == '/ibc.core.channel.v1.MsgRecvPacket'):
                                return 'receive_packet'
                            else:
                                return option['value']
        elif(len(tx['data']['logs']) >= 2 and len(tx['data']['logs']) <= 6): # TODO: MAKE THIS EXPLICIT (LEFT IMPLICIT FOR TESTING PURPOSES -- WORKS FINE)
            ans = []
            for i in tx['data']['logs']:
                for j in i['events']:
                    if(j['type'] == 'message'):
                        for k in j['attributes']:
                            if(k['key'] == 'action'):
                                action = k['value']
                            if(action == '/cosmos.gov.v1beta1.MsgVote'):
                                ans.append('proposal')
                            elif(action == '/cosmos.bank.v1beta1.MsgSend'):
                                ans.append('transfer')
                            elif(action == '/cosmos.distribution.v1beta1.MsgWithdrawDelegatorReward'):
                                ans.append('reward')
                            elif(action == '/cosmos.staking.v1beta1.MsgDelegate'):
                                ans.append('delegate')
                            elif(action == '/cosmos.staking.v1beta1.MsgUndelegate'):
                                ans.append('undelegate')
                            elif(action == '/ibc.applications.transfer.v1.MsgTransfer'):
                                ans.append('ibc_transfer')
                            elif(action == '/ibc.core.client.v1.MsgUpdateClient'):
                                continue
                            elif(action == '/osmosis.gamm.v1beta1.MsgSwapExactAmountIn'):
                                ans.append('lp_swap')
                            elif(action == '/ibc.core.channel.v1.MsgRecvPacket'):
                                ans.append('receive_packet')
                            else:
                                ans.append(k['value'])
            return ans              
        else:
            return 'failed'

    def get_reward(self, tx:dict) -> float:
        denom = tx['data']['tx']['auth_info']['fee']['amount'][0]['denom']
        for i in tx['data']['logs'][0]['events']:
            if(i['type'] == 'withdraw_rewards'):
                for j in i['attributes']:
                    if(j['key'] == 'amount'):
                        try:
                            return float(j['value'].replace(denom, '')) / 1000000
                        except ValueError:      
                            try:
                                return float(j['value'].split(',')[1].replace(denom, '')) / 1000000
                            except: 
                                return 0

    def get_price(self) -> float:
        res = self.collection.find_one({'symbol': self.symbol})
        return float(json.loads(requests.get(res['endpoints']['price']).content)[res['name']]['usd'])

    def calc_fiat(self, amount:float, timestamp:float, rec:bool, fees:float):
        res = self.collection.find_one({'symbol': self.symbol})
        url = res['endpoints']['historical_price']
        
        date = timestamp[0].split('-')
        time = timestamp[1].split(':')
        dt = datetime(year=int(date[0]), month=int(date[1]), day=int(date[2]), hour=int(time[0]), minute=int(time[1]), second=int(time[2]))
        
        timestamp = int(dt.replace(tzinfo=timezone.utc).timestamp())

        if(rec):
            try:
                ans = json.loads(requests.get(url.replace('<NAME>', res['name']).replace('<FIAT>', 'usd').replace('<FROM>', str(timestamp)).replace('<TO>', str(timestamp+2500))).content)
                price = float(ans['prices'][0][1])
            except IndexError:
                ans = json.loads(requests.get(url.replace('<NAME>', res['name']).replace('<FIAT>', 'usd').replace('<FROM>', str(timestamp)).replace('<TO>', str(timestamp+5000))).content)
                price = '{:.2f}'.format(float(ans['prices'][0][1]))

            self.init_amount += amount * float(price) - fees
            self.amount += amount - fees
        else:
            self.amount -= amount + fees



    def iterate_txs(self, response:list) -> dict:

        #   TODO
        #   FIX BUG WITH AMOUNT SHOWING NEGATIVE;
        #   RE-CONSTRUCT THE CALCULATED VALUE SCHEME TO SHOW ONLY THE FINAL AMOUNTS AND CALCULATE VALUE AFTERWARDS;        

        for tx in response:
            amount = 0.0
            rewards = 0.0
            fees = 0.0
            timestamp = ''
            receiver = None

            self.txs += 1
            timestamp = self.get_metadata(tx)
            fees = self.get_fees(tx)
            action = self.get_action(tx)
            if(type(action) == list):
                for i in action:
                    if(i == 'failed'):
                        self.failed += 1
                        self.amount -= fees

                    if(i == 'proposal'):
                        receiver = False
                        self.proposals += 1
                        self.votes.append({'proposal': tx['data']['logs'][0]['events'][1]['attributes'][1]['value'], 'option': tx['data']['logs'][0]['events'][1]['attributes'][0]['value'].split(':')[1].split(',')[0]})
                        self.amount -= fees

                    if(i == 'reward'):
                        receiver = True
                        self.rewards += self.get_reward(tx)
                        self.amount += rewards - fees
                            
                    if(i == 'transfer'):
                        receiver = self.is_receiver(tx)
                        if(receiver):
                            self.amount += self.get_amount(tx) - fees
                        else:
                            self.amount -= self.get_amount(tx) + fees
                        # amount = self.get_amount(tx)
                        # self.calc_fiat(amount=amount, timestamp=timestamp, rec=receiver, fees=fees)

                    if(i == 'ibc_transfer'):
                        receiver = self.is_receiver(tx)
                        if(receiver):
                            self.amount += self.get_amount(tx) - fees                            
                        else:
                            self.amount -= self.get_amount(tx) + fees
                        # amount = self.get_amount(tx)
                        # self.calc_fiat(amount=amount, timestamp=timestamp, rec=receiver, fees=fees)

                    if(i == 'delegate'):
                        self.amount -= fees
                        self.delegated += self.get_amount(tx)

                    if(i == 'undelegate'):
                        self.amount -= fees
                        self.delegated -= self.get_amount(tx)
                        for j in tx['data']['logs'][0]['events']:
                            if(j['type'] == 'unbond'):
                                for k in j['attributes']:
                                    if(k['key'] == 'completion_time'):
                                        unbond_time = k['value'].replace('T', ' ').replace('Z', '')
                                        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                        t1 = datetime.strptime(unbond_time, "%Y-%m-%d %H:%M:%S")
                                        t2 = datetime.strptime(current_time, "%Y-%m-%d %H:%M:%S")
                                        if(max(t1,t2) == t1):                            
                                            self.unbonding += self.get_amount(tx)

                    self.fees += fees
            else:
                if(action == 'failed'):
                    self.failed += 1
                    self.amount -= fees

                if(action == 'proposal'):
                    receiver = False
                    self.proposals += 1
                    option = tx['data']['logs'][0]['events'][1]['attributes'][0]['value'].split(':')[1].split(',')[0]
                    if(option == '1'):
                        option = 'YES'
                    elif(option == '2'):
                        option = 'NO'
                    elif(option == '3'):
                        option = 'ABSTAIN'
                    elif(option == '4'):
                        option = 'NO with VETO'
                    self.votes.append({'proposal': tx['data']['logs'][0]['events'][1]['attributes'][1]['value'], 'option': option})
                    self.amount -= fees

                if(action == 'reward'):
                    receiver = True
                    self.rewards += self.get_reward(tx)
                    self.amount += rewards - fees
                        
                if(action == 'transfer'):
                    receiver = self.is_receiver(tx)
                    if(receiver):
                        self.amount += self.get_amount(tx) - fees
                    else:
                        self.amount -= self.get_amount(tx) + fees
                    # amount = self.get_amount(tx)
                    # self.calc_fiat(amount=amount, timestamp=timestamp, rec=receiver, fees=fees)

                if(action == 'ibc_transfer'):
                    receiver = self.is_receiver(tx)
                    if(receiver):
                        self.amount += self.get_amount(tx) - fees
                    else:
                        self.amount -= self.get_amount(tx) + fees
                    # amount = self.get_amount(tx)
                    # self.calc_fiat(amount=amount, timestamp=timestamp, rec=receiver, fees=fees)
                
                if(action == 'delegate'):
                    self.amount -= fees
                    self.delegated += self.get_amount(tx)

                if(action == 'undelegate'):
                    self.amount -= fees
                    self.delegated -= self.get_amount(tx)
                    for i in tx['data']['logs'][0]['events']:
                        if(i['type'] == 'unbond'):
                            for j in i['attributes']:
                                if(j['key'] == 'completion_time'):
                                    unbond_time = j['value'].replace('T', ' ').replace('Z', '')
                                    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    t1 = datetime.strptime(unbond_time, "%Y-%m-%d %H:%M:%S")
                                    t2 = datetime.strptime(current_time, "%Y-%m-%d %H:%M:%S")
                                    if(max(t1,t2) == t1):                            
                                        self.unbonding += self.get_amount(tx)

                if(action == 'receive_packet'):
                    continue

                self.fees += fees
            
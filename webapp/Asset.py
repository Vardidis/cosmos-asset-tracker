import requests
import json
import pymongo
from datetime import datetime

class Asset:
    '''
    Representation of summary of data from all the batches of transactions.

    Each Asset is represented by an object to assist calculation of its attributes.
    Asset objects are then serialized into Django models in order to get passed on the front-end.
    '''

    def __init__(self, symbol:str, address:str, mongo_uri:str) -> None:
        self.symbol = symbol
        self.address = address
        self.balance = 0.0
        self.rewards = 0.0
        self.fees = 0.0
        self.unbonding = 0.0
        self.delegated = 0.0
        self.txs = 0
        self.failed = 0
        self.proposals = 0
        self.votes = []
        self.test = []
        self.denom = 'u' + self.symbol.lower()
        # MongoDB connection to fetch asset details e.g. icon, api endpoints, token name, etc.
        client = pymongo.MongoClient(mongo_uri)
        db = client['asset_tracker']
        self.collection = db['staging']

    def fetch_txs(self) -> None:
        '''
        Loops through one or more 50 transaction batches for a spesific Asset.

        Each batch of transactions is then passed to `iterate_txs()` method which is responsible
        for collecting the necessary data from each transaction, finally assigning values to
        each Asset object attribute.
        '''    
        # `offset` (int): specifies the offset for each 50 transaction batch fetching
        flag = True
        offset = 0

        # `assetDB` (dict): Calls the cluster for details on a spesific Asset by its token name. Returns
        # a reference to the object retrieved.
        # `mint_api` (str): Specifies the URL for Mintscan API endpoint returning a 50 transaction
        # batch.
        assetDB = self.collection.find_one({'symbol': self.symbol})
        mint_api = assetDB['endpoints']['mint_name']

        while(flag):
            url = 'https://<API>.cosmostation.io/v1/account/new_txs/<ADDRESS>?limit=50&from=<FLOOR>'.replace('<FLOOR>', str(offset)).replace('<ADDRESS>', self.address).replace('<API>', mint_api)
            res = json.loads(requests.get(url).content)

            try:
                assert (res != [])
            except AssertionError:
                continue

            flag = not (len(res) < 50)
            offset = res[-1]['header']['id']
            self._iterate_txs(res) 

    def _decide_action(self, action:str) -> str:
        if(action == '/cosmos.gov.v1beta1.MsgVote'):
            return 'proposal'

        if(action == '/cosmos.bank.v1beta1.MsgSend'):
            return 'transfer'

        if(action == '/cosmos.distribution.v1beta1.MsgWithdrawDelegatorReward'):
            return 'reward'

        if(action == '/cosmos.staking.v1beta1.MsgDelegate'):
            return 'delegate'

        if(action == '/cosmos.staking.v1beta1.MsgUndelegate'):
            return 'undelegate'

        if(action == '/ibc.applications.transfer.v1.MsgTransfer'):
            return 'ibc_transfer'

        if(action == '/ibc.core.client.v1.MsgUpdateClient'):
            return 'client_update'

        if(action == '/osmosis.gamm.v1beta1.MsgSwapExactAmountIn'):
            return 'lp_swap'

        if(action == '/ibc.core.channel.v1.MsgRecvPacket'):
            return 'receive_packet'

        if(action == '/cosmwasm.wasm.v1.MsgExecuteContract'):
            return 'execute_contract'

        if(action == '/ibc.core.channel.v1.MsgAcknowledgement'):
            return 'acknowledgement'

    def _get_action(self, tx:dict) -> str or list[str]:
        log_length = len(tx['data']['logs'])
        if(log_length == 1):
            events = tx['data']['logs'][0]['events']
            for index in events:
                if(index['type'] == 'message'):
                    for option in index['attributes']:
                        if(option['key'] == 'action'):
                            action = option['value']   
                            return self._decide_action(action)                         
        elif(log_length > 0 and log_length < 6):
            aux = []
            for index in tx['data']['logs']:
                for option in index['events']:
                    if(option['type'] == 'message'):
                        for i in option['attributes']:
                            if(i['key'] == 'action'):
                                action = i['value']       
                                aux.append(self._decide_action(action))
            return aux
        else:
            return 'failed'

    def _get_timestamp(self, tx:dict) -> str:
        return tx['header']['timestamp'].replace('Z', '').replace('T', ' ')

    def _is_receiver(self, tx:dict, action:str) -> bool:
        if(action != 'receive_packet'):
            for index in tx['data']['logs'][0]['events']:
                for option in index['attributes']:
                    if(option['key'] == 'receiver'):
                        return option['value'] == self.address      
        else:
            for index in tx['data']['logs']:
                for option in index['events']:
                    if(option['type'] == 'recv_packet'):
                        for i in option['attributes']:
                            if(i['key'] == 'packet_data'):
                                receiver = json.loads(i['value'].replace('\"\\/', ''))['receiver']
                                return receiver == self.address

    def _get_reward(self, tx:dict) -> float:
        self.denom = tx['data']['tx']['auth_info']['fee']['amount'][0]['denom']
        for index in tx['data']['logs'][0]['events']:
            if(index['type'] == 'withdraw_rewards'):
                for option in index['attributes']:
                    if(option['key'] == 'amount'):
                        try:                            
                            return float(option['value'].replace(self.denom, '')) / 1000000
                        except ValueError:      
                            try:
                                return float(option['value'].split(',')[1].replace(self.denom, '')) / 1000000
                            except: 
                                return 0

    def _get_price(self) -> float:
        assetDB = self.collection.find_one({'symbol': self.symbol})
        return float(json.loads(requests.get(assetDB['endpoints']['price']).content)[assetDB['name']]['usd'])

    def _get_amount(self, tx:dict) -> float:
        
        try:
            amount = float(tx['data']['tx']['body']['messages'][0]['token']['amount']) / 1000000
        except KeyError:
            try:
                amount = float(tx['data']['tx']['body']['messages'][0]['amount'][0]['amount']) / 1000000
            except KeyError:
                try:
                    amount = float(tx['data']['tx']['body']['messages'][0]['amount']['amount']) / 1000000
                except KeyError:  
                    try:              
                        logs = tx['data']['logs']
                        for index in logs:
                            for i in index['events']:
                                if(i['type'] == 'recv_packet'):
                                    for option in i['attributes']:
                                        if(option['key'] == 'packet_data'):    
                                            amount = float(json.loads(option['value'].replace('\"\\/', ''))['amount']) / 1000000                   
                    except:
                        amount = 0
        except:
            amount = 0
        finally:            
            return amount

    def _get_fees(self, tx:dict) -> float:
        try:
            return float(tx['data']['tx']['auth_info']['fee']['amount'][0]['amount']) / 1000000
        except IndexError:
            return 0.0

    def _calc_data(self, tx:dict, action:str) -> None:
        fees = self._get_fees(tx)
        self.fees += fees        
        if(action == 'failed'):
            self.failed += 1
            #self.balance -= fees
            return

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
            #self.balance -= fees
            return

        if(action == 'reward'):
            receiver = True
            reward = self._get_reward(tx)
            self.rewards += reward
            amount = reward - fees
            #self.balance += amount
            return
                
        if(action == 'transfer' or action == 'ibc_transfer'):
            #receiver = self._is_receiver(tx, action)
            amount = self._get_amount(tx)          
            self.test.append(tx['data']['txhash'] + ' ' + str(amount) + ' ' + str(fees))

            # if(receiver):
            #     self.balance += amount - fees
            # else:
            #     self.balance -= amount + fees
            # return
        
        if(action == 'delegate'):
            amount = self._get_amount(tx)
            self.delegated += amount
            #self.balance -= amount + fees
            # for index in tx['data']['logs'][0]['events']:
            #     if(index['type'] == 'transfer'):
            #         for option in index['attributes']:
            #             if(option['key'] == 'recipient'):
            #                 receiver = option['value'] == self.address
            #             if(option['key'] == 'amount'):
            #                 self.balance += float(option['value'].replace(self.denom, '')) / 1000000
                        
            return

        if(action == 'undelegate'):
            amount = self._get_amount(tx)
            #self.balance -= fees
            self.delegated -= amount
            for i in tx['data']['logs'][0]['events']:
                if(i['type'] == 'unbond'):
                    for j in i['attributes']:
                        if(j['key'] == 'completion_time'):
                            unbond_time = j['value'].replace('T', ' ').replace('Z', '')
                            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            t1 = datetime.strptime(unbond_time, "%Y-%m-%d %H:%M:%S")
                            t2 = datetime.strptime(current_time, "%Y-%m-%d %H:%M:%S")
                            if(max(t1,t2) == t1):                            
                                self.unbonding += amount
            return

        if(action == 'execute_contract'):            
            return

        # if(action == 'receive_packet'): 
        #     if(self._is_receiver(tx, action)):
        #         self.balance += self._get_amount(tx) - fees
        #     else:
        #         self.balance -= self._get_amount(tx) + fees

    def _iterate_txs(self, batch:list) -> None:
        
        for tx in batch:
            self.txs += 1            
            action = self._get_action(tx)
            
            if(type(action) == list):
                for i in action:
                    self._calc_data(tx, i)
            else:
                self._calc_data(tx, action)

class Atom(Asset):

    def __init__(self, symbol:str, address:str, mongo_uri:str):
        super().__init__(symbol, address, mongo_uri)

    def get_balance(self):
        url = 'https://api.cosmos.network/cosmos/bank/v1beta1/balances/' + self.address
        res = json.loads(requests.get(url).content)
        self.balance = float(res['balances'][0]['amount']) / 1000000

class Juno(Asset):

    def __init__(self, symbol:str, address:str, mongo_uri:str):
        super().__init__(symbol, address, mongo_uri)

    def get_balance(self):
        url = 'https://lcd-juno.cosmostation.io/cosmos/bank/v1beta1/balances/' + self.address
        res = json.loads(requests.get(url).content)
        self.balance = float(res['balances'][0]['amount']) / 1000000

class Osmo(Asset):

    def __init__(self, symbol:str, address:str, mongo_uri:str):
        super().__init__(symbol, address, mongo_uri)

    def get_balance(self):
        url = 'https://lcd-osmosis.keplr.app/bank/balances/' + self.address
        res = json.loads(requests.get(url).content)
        self.balance = float(res['balances'][0]['amount']) / 1000000
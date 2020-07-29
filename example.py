# https://stackoverflow.com/questions/57618971/how-do-i-get-my-accounts-positions-at-interactive-brokers-using-python-api
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.common import * #for TickerId type
import pandas as pd


class ib_class(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.all_positions = pd.DataFrame([], columns = ['Account','Symbol', 'Quantity', 'Average Cost'])

    def position(self, account, contract, pos, avgCost):
        index = str(account)+str(contract.symbol)
        self.all_positions.loc[index]=account,contract.symbol,pos,avgCost

    def error(self, reqId:TickerId, errorCode:int, errorString:str):
        if reqId > -1:
            print("Error. Id: " , reqId, " Code: " , errorCode , " Msg: " , errorString)

    def positionEnd(self):
        self.disconnect()

ib_api = ib_class()
ib_api.connect("127.0.0.1", 7496, 0)
ib_api.reqPositions()
current_positions = ib_api.all_positions
ib_api.run()
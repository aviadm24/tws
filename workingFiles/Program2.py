"""
Copyright (C) 2019 Interactive Brokers LLC. All rights reserved. This code is subject to the terms
 and conditions of the IB API Non-Commercial License or the IB API Commercial License, as applicable.
"""
# https://algotrading101.com/learn/interactive-brokers-python-api-native-guide/

import argparse
import datetime
import collections
import inspect

import logging
import time
import os.path
import queue

from ibapi import wrapper
from ibapi import utils
from ibapi.client import EClient
from ibapi.utils import iswrapper

# types
from ibapi.common import * # @UnusedWildImport
from ibapi.order_condition import * # @UnusedWildImport
from ibapi.contract import * # @UnusedWildImport
from ibapi.order import * # @UnusedWildImport
from ibapi.order_state import * # @UnusedWildImport
from ibapi.execution import Execution
from ibapi.execution import ExecutionFilter
from ibapi.commission_report import CommissionReport
from ibapi.ticktype import * # @UnusedWildImport
from ibapi.tag_value import TagValue

from ibapi.account_summary_tags import *

# from ContractSamples import ContractSamples
from Contracts import Contracts
# from OrderSamples import OrderSamples
from Orders import Orders
# from AvailableAlgoParams import AvailableAlgoParams
# from ScannerSubscriptionSamples import ScannerSubscriptionSamples
# from FaAllocationSamples import FaAllocationSamples
# from ibapi.scanner import ScanData
import datetime as dt
RUNTIME = 10


def SetupLogger():
    if not os.path.exists("log"):
        os.makedirs("log")

    time.strftime("pyibapi.%Y%m%d_%H%M%S.log")

    recfmt = '(%(threadName)s) %(asctime)s.%(msecs)03d %(levelname)s %(filename)s:%(lineno)d %(message)s'

    timefmt = '%y%m%d_%H:%M:%S'

    # logging.basicConfig( level=logging.DEBUG,
    #                    format=recfmt, datefmt=timefmt)
    logging.basicConfig(filename=time.strftime("log/pyibapi.%y%m%d_%H%M%S.log"),
                        filemode="w",
                        level=logging.INFO,
                        format=recfmt, datefmt=timefmt)
    logger = logging.getLogger()
    console = logging.StreamHandler()
    console.setLevel(logging.ERROR)
    logger.addHandler(console)


def printWhenExecuting(fn):
    def fn2(self):
        print("   doing", fn.__name__)
        fn(self)
        print("   done w/", fn.__name__)

    return fn2


def printinstance(inst:Object):
    attrs = vars(inst)
    print(', '.join("%s: %s" % item for item in attrs.items()))


class Activity(Object):
    def __init__(self, reqMsgId, ansMsgId, ansEndMsgId, reqId):
        self.reqMsdId = reqMsgId
        self.ansMsgId = ansMsgId
        self.ansEndMsgId = ansEndMsgId
        self.reqId = reqId


class RequestMgr(Object):
    def __init__(self):
        # I will keep this simple even if slower for now: only one list of
        # requests finding will be done by linear search
        self.requests = []

    def addReq(self, req):
        self.requests.append(req)

    def receivedMsg(self, msg):
        pass


# ! [socket_declare]
class TestClient(EClient):
    def __init__(self, wrapper):
        EClient.__init__(self, wrapper)
        # ! [socket_declare]

        # how many times a method is called to see test coverage
        self.clntMeth2callCount = collections.defaultdict(int)
        self.clntMeth2reqIdIdx = collections.defaultdict(lambda: -1)
        self.reqId2nReq = collections.defaultdict(int)
        self.setupDetectReqId()

    def countReqId(self, methName, fn):
        def countReqId_(*args, **kwargs):
            self.clntMeth2callCount[methName] += 1
            idx = self.clntMeth2reqIdIdx[methName]
            if idx >= 0:
                sign = -1 if 'cancel' in methName else 1
                self.reqId2nReq[sign * args[idx]] += 1
            return fn(*args, **kwargs)

        return countReqId_

    def setupDetectReqId(self):
        methods = inspect.getmembers(EClient, inspect.isfunction)
        for (methName, meth) in methods:
            if methName != "send_msg":
                # don't screw up the nice automated logging in the send_msg()
                self.clntMeth2callCount[methName] = 0
                # logging.debug("meth %s", name)
                sig = inspect.signature(meth)
                for (idx, pnameNparam) in enumerate(sig.parameters.items()):
                    (paramName, param) = pnameNparam # @UnusedVariable
                    if paramName == "reqId":
                        self.clntMeth2reqIdIdx[methName] = idx

                setattr(TestClient, methName, self.countReqId(methName, meth))

                # print("TestClient.clntMeth2reqIdIdx", self.clntMeth2reqIdIdx)


# ! [ewrapperimpl]
class TestWrapper(wrapper.EWrapper):
    # ! [ewrapperimpl]
    def __init__(self):
        wrapper.EWrapper.__init__(self)

        self.wrapMeth2callCount = collections.defaultdict(int)
        self.wrapMeth2reqIdIdx = collections.defaultdict(lambda: -1)
        self.reqId2nAns = collections.defaultdict(int)
        self.setupDetectWrapperReqId()

    # TODO: see how to factor this out !!

    def countWrapReqId(self, methName, fn):
        def countWrapReqId_(*args, **kwargs):
            self.wrapMeth2callCount[methName] += 1
            idx = self.wrapMeth2reqIdIdx[methName]
            if idx >= 0:
                self.reqId2nAns[args[idx]] += 1
            return fn(*args, **kwargs)

        return countWrapReqId_

    def setupDetectWrapperReqId(self):

        methods = inspect.getmembers(wrapper.EWrapper, inspect.isfunction)
        for (methName, meth) in methods:
            self.wrapMeth2callCount[methName] = 0
            # logging.debug("meth %s", name)
            sig = inspect.signature(meth)
            for (idx, pnameNparam) in enumerate(sig.parameters.items()):
                (paramName, param) = pnameNparam # @UnusedVariable
                # we want to count the errors as 'error' not 'answer'
                if 'error' not in methName and paramName == "reqId":
                    self.wrapMeth2reqIdIdx[methName] = idx

            setattr(TestWrapper, methName, self.countWrapReqId(methName, meth))

            # print("TestClient.wrapMeth2reqIdIdx", self.wrapMeth2reqIdIdx)


class TestApp(TestWrapper, TestClient):
    def __init__(self, stock, trail, amount, delta, start_time, gui_queue):
        TestWrapper.__init__(self)
        TestClient.__init__(self, wrapper=self)
        # ! [socket_init]
        self.nKeybInt = 0
        self.started = False
        self.nextValidOrderId = None
        self.permId2ord = {}
        self.reqId2nErr = collections.defaultdict(int)
        self.globalCancelOnly = False
        self.simplePlaceOid = None

        self.price = 0
        self.priceList = []
        self.delta = delta
        self.start_time = start_time
        self.stock_dir = 'up'
        self.pos = 0
        self.StopPrice = 0
        self.filled = 0
        self.mktCapPrice = 0
        self.sold = False
        self.bought = False
        self.gui_queue = gui_queue

        self.stock = stock
        self.trail = trail
        self.amount = amount
        self.nextSellingPrice = 0
        self.id = 0
        self.status = ''
        self.message = ''
        self.first_buy = False
        self.second_buy = False

    def dumpTestCoverageSituation(self):
        for clntMeth in sorted(self.clntMeth2callCount.keys()):
            logging.debug("ClntMeth: %-30s %6d" % (clntMeth,
                                                   self.clntMeth2callCount[clntMeth]))

        for wrapMeth in sorted(self.wrapMeth2callCount.keys()):
            logging.debug("WrapMeth: %-30s %6d" % (wrapMeth,
                                                   self.wrapMeth2callCount[wrapMeth]))

    def dumpReqAnsErrSituation(self):
        logging.debug("%s\t%s\t%s\t%s" % ("ReqId", "#Req", "#Ans", "#Err"))
        for reqId in sorted(self.reqId2nReq.keys()):
            nReq = self.reqId2nReq.get(reqId, 0)
            nAns = self.reqId2nAns.get(reqId, 0)
            nErr = self.reqId2nErr.get(reqId, 0)
            logging.debug("%d\t%d\t%s\t%d" % (reqId, nReq, nAns, nErr))

    @iswrapper
    # ! [connectack]
    def connectAck(self):
        if self.asynchronous:
            self.startApi()

    # ! [connectack]

    @iswrapper
    # ! [nextvalidid]
    def nextValidId(self, orderId: int):
        super().nextValidId(orderId)

        logging.debug("setting nextValidOrderId: %d", orderId)
        self.nextValidOrderId = orderId
        print("NextValidId:", orderId)
    # ! [nextvalidid]

        # we can start now
        self.start()

    def start(self):
        if self.started:
            return

        self.started = True

        if self.globalCancelOnly:
            print("Executing GlobalCancel only")
            self.reqGlobalCancel()
        else:
            print("Executing requests")
            #self.reqGlobalCancel()
            #self.marketDataTypeOperations()
            self.accountOperations_req()
            #self.tickDataOperations_req()
            #self.marketDepthOperations_req()
            #self.realTimeBarsOperations_req()
            #self.historicalDataOperations_req()
            #self.optionsOperations_req()
            #self.marketScannersOperations_req()
            #self.fundamentalsOperations_req()
            #self.bulletinsOperations_req()
            #self.contractOperations()
            #self.newsOperations_req()
            #self.miscelaneousOperations()
            #self.linkingOperations()
            #self.financialAdvisorOperations()
            self.orderOperations_req()
            #self.rerouteCFDOperations()
            #self.marketRuleOperations()
            #self.pnlOperations_req()
            #self.histogramOperations_req()
            #self.continuousFuturesOperations_req()
            #self.historicalTicksOperations()
            #self.tickByTickOperations_req()
            #self.whatIfOrderOperations()
            
            print("Executing requests ... finished")

    def keyboardInterrupt(self):
        self.nKeybInt += 1
        if self.nKeybInt == 1:
            self.stop()
        else:
            print("Finishing test")
            self.done = True

    def stop(self):
        print("Executing cancels")
        #self.orderOperations_cancel()
        #self.accountOperations_cancel()
        #self.tickDataOperations_cancel()
        self.marketDepthOperations_cancel()
        #self.realTimeBarsOperations_cancel()
        #self.historicalDataOperations_cancel()
        #self.optionsOperations_cancel()
        #self.marketScanners_cancel()
        #self.fundamentalsOperations_cancel()
        #self.bulletinsOperations_cancel()
        #self.newsOperations_cancel()
        #self.pnlOperations_cancel()
        #self.histogramOperations_cancel()
        #self.continuousFuturesOperations_cancel()
        #self.tickByTickOperations_cancel()
        print("Executing cancels ... finished")

    @printWhenExecuting
    def marketDepthOperations_cancel(self):
        # Canceling the Deep Book request
        # ! [cancelmktdepth]
        self.cancelMktDepth(2001, False)
        self.cancelMktDepth(2002, True)
        # ! [cancelmktdepth]

    def nextOrderId(self):
        oid = self.nextValidOrderId
        self.nextValidOrderId += 1
        return oid

    @iswrapper
    # ! [error]
    def error(self, reqId: TickerId, errorCode: int, errorString: str):
        super().error(reqId, errorCode, errorString)
        print("Error. Id:", reqId, "Code:", errorCode, "Msg:", errorString)

    # ! [error] self.reqId2nErr[reqId] += 1


    @iswrapper
    def winError(self, text: str, lastError: int):
        super().winError(text, lastError)

    @iswrapper
    # ! [openorder]
    def openOrder(self, orderId: OrderId, contract: Contract, order: Order,
                  orderState: OrderState):
        super().openOrder(orderId, contract, order, orderState)
        # print("OpenOrder. PermId: ", order.permId, "ClientId:", order.clientId, " OrderId:", orderId,
        #       "Account:", order.account, "Symbol:", contract.symbol, "SecType:", contract.secType,
        #       "Exchange:", contract.exchange, "Action:", order.action, "OrderType:", order.orderType,
        #       "TotalQty:", order.totalQuantity, "CashQty:", order.cashQty,
        #       "LmtPrice:", order.lmtPrice, "AuxPrice:", order.auxPrice, "Status:", orderState.status)

        order.contract = contract
        self.permId2ord[order.permId] = order
    # ! [openorder]

    @iswrapper
    # ! [openorderend]
    def openOrderEnd(self):
        super().openOrderEnd()
        # print("OpenOrderEnd")

        logging.debug("Received %d openOrders", len(self.permId2ord))
    # ! [openorderend]

    @iswrapper
    # ! [orderstatus]
    def orderStatus(self, orderId: OrderId, status: str, filled: float,
                    remaining: float, avgFillPrice: float, permId: int,
                    parentId: int, lastFillPrice: float, clientId: int,
                    whyHeld: str, mktCapPrice: float):
        super().orderStatus(orderId, status, filled, remaining,
                            avgFillPrice, permId, parentId, lastFillPrice, clientId, whyHeld, mktCapPrice)
        # print('^^^^^^^^^^^^^^^^^^^^^^^filled {}^^^^^^^^^^^^^^^^'.format(filled))
        self.filled = filled
        self.mktCapPrice = mktCapPrice
        self.id = orderId
        self.status = status

        # print("order: ", orderId, "status: ", status)

        # print("OrderStatus. Id:", orderId, "Status:", status, "Filled:", filled,
        #       "Remaining:", remaining, "AvgFillPrice:", avgFillPrice,
        #       "PermId:", permId, "ParentId:", parentId, "LastFillPrice:",
        #       lastFillPrice, "ClientId:", clientId, "WhyHeld:",
        #       whyHeld, "MktCapPrice:", mktCapPrice)
    # ! [orderstatus]

    @printWhenExecuting
    def accountOperations_req(self):
        # Requesting managed accounts
        self.reqManagedAccts()
        self.reqPositions()

    @iswrapper
    # ! [updateaccountvalue]
    def updateAccountValue(self, key: str, val: str, currency: str,
                           accountName: str):
        super().updateAccountValue(key, val, currency, accountName)
        # print("UpdateAccountValue. Key:", key, "Value:", val,
        #       "Currency:", currency, "AccountName:", accountName)
    # ! [updateaccountvalue]

    @iswrapper
    # ! [updateportfolio]
    def updatePortfolio(self, contract: Contract, position: float,
                        marketPrice: float, marketValue: float,
                        averageCost: float, unrealizedPNL: float,
                        realizedPNL: float, accountName: str):
        super().updatePortfolio(contract, position, marketPrice, marketValue,
                                averageCost, unrealizedPNL, realizedPNL, accountName)
        print("Position:", position)
        # print("UpdatePortfolio.", "Symbol:", contract.symbol, "SecType:", contract.secType, "Exchange:",
        #       contract.exchange, "Position:", position, "MarketPrice:", marketPrice,
        #       "MarketValue:", marketValue, "AverageCost:", averageCost,
        #       "UnrealizedPNL:", unrealizedPNL, "RealizedPNL:", realizedPNL,
        #       "AccountName:", accountName)
    # ! [updateportfolio]




    def marketDataTypeOperations(self):
        # ! [reqmarketdatatype]
        # Switch to live (1) frozen (2) delayed (3) delayed frozen (4).
        self.reqMarketDataType(MarketDataTypeEnum.DELAYED)
        # ! [reqmarketdatatype]

    @iswrapper
    # ! [marketdatatype]
    def marketDataType(self, reqId: TickerId, marketDataType: int):
        super().marketDataType(reqId, marketDataType)
        # print("MarketDataType. ReqId:", reqId, "Type:", marketDataType)
    # ! [marketdatatype]

    @printWhenExecuting
    def tickDataOperations_req(self):
        self.reqMarketDataType(MarketDataTypeEnum.DELAYED_FROZEN)
        self.reqMktData(1000, Contracts.AnyStock(self.stock), "", False, False, [])
        # Requesting real time market data

        # # ! [reqmktdata]
        # self.reqMktData(1000, ContractSamples.USStockAtSmart(), "", False, False, [])
        # self.reqMktData(1001, ContractSamples.StockComboContract(), "", False, False, [])
        # # ! [reqmktdata]
        #
        # # ! [reqmktdata_snapshot]
        # self.reqMktData(1002, ContractSamples.FutureComboContract(), "", True, False, [])
        # # ! [reqmktdata_snapshot]
        #
        # # ! [regulatorysnapshot]
        # # Each regulatory snapshot request incurs a 0.01 USD fee
        # self.reqMktData(1003, ContractSamples.USStock(), "", False, True, [])
        # # ! [regulatorysnapshot]
        #
        # # ! [reqmktdata_genticks]
        # # Requesting RTVolume (Time & Sales), shortable and Fundamental Ratios generic ticks
        # self.reqMktData(1004, ContractSamples.USStockAtSmart(), "233,236,258", False, False, [])
        # # ! [reqmktdata_genticks]
        #
        # # ! [reqmktdata_contractnews]
        # # Without the API news subscription this will generate an "invalid tick type" error
        # self.reqMktData(1005, ContractSamples.USStockAtSmart(), "mdoff,292:BRFG", False, False, [])
        # self.reqMktData(1006, ContractSamples.USStockAtSmart(), "mdoff,292:BRFG+DJNL", False, False, [])
        # self.reqMktData(1007, ContractSamples.USStockAtSmart(), "mdoff,292:BRFUPDN", False, False, [])
        # self.reqMktData(1008, ContractSamples.USStockAtSmart(), "mdoff,292:DJ-RT", False, False, [])
        # # ! [reqmktdata_contractnews]
        #
        #
        # # ! [reqmktdata_broadtapenews]
        # self.reqMktData(1009, ContractSamples.BRFGbroadtapeNewsFeed(), "mdoff,292", False, False, [])
        # self.reqMktData(1010, ContractSamples.DJNLbroadtapeNewsFeed(), "mdoff,292", False, False, [])
        # self.reqMktData(1011, ContractSamples.DJTOPbroadtapeNewsFeed(), "mdoff,292", False, False, [])
        # self.reqMktData(1012, ContractSamples.BRFUPDNbroadtapeNewsFeed(), "mdoff,292", False, False, [])
        # # ! [reqmktdata_broadtapenews]
        #
        # # ! [reqoptiondatagenticks]
        # # Requesting data for an option contract will return the greek values
        # self.reqMktData(1013, ContractSamples.OptionWithLocalSymbol(), "", False, False, [])
        # self.reqMktData(1014, ContractSamples.FuturesOnOptions(), "", False, False, []);
        #
        # # ! [reqoptiondatagenticks]
        #
        # # ! [reqfuturesopeninterest]
        # self.reqMktData(1015, ContractSamples.SimpleFuture(), "mdoff,588", False, False, [])
        # # ! [reqfuturesopeninterest]
        #
        # # ! [reqmktdatapreopenbidask]
        # self.reqMktData(1016, ContractSamples.SimpleFuture(), "", False, False, [])
        # # ! [reqmktdatapreopenbidask]
        #
        # # ! [reqavgoptvolume]
        # self.reqMktData(1017, ContractSamples.USStockAtSmart(), "mdoff,105", False, False, [])
        # # ! [reqavgoptvolume]
        #
        # # ! [reqsmartcomponents]
        # # Requests description of map of single letter exchange codes to full exchange names
        # self.reqSmartComponents(1018, "a6")
        # # ! [reqsmartcomponents]
        

    @printWhenExecuting
    def tickDataOperations_cancel(self):
        # Canceling the market data subscription
        # ! [cancelmktdata]
        self.cancelMktData(1000)
        self.cancelMktData(1001)
        # ! [cancelmktdata]

        self.cancelMktData(1004)
        
        self.cancelMktData(1005)
        self.cancelMktData(1006)
        self.cancelMktData(1007)
        self.cancelMktData(1008)
        
        self.cancelMktData(1009)
        self.cancelMktData(1010)
        self.cancelMktData(1011)
        self.cancelMktData(1012)
        
        self.cancelMktData(1013)
        self.cancelMktData(1014)
        
        self.cancelMktData(1015)
        
        self.cancelMktData(1016)
        
        self.cancelMktData(1017)

    def position(self, account: str, contract: Contract, position: float,
                 avgCost: float):
        super().position(account, contract, position, avgCost)
        # print("contract: ", contract)
        if contract.symbol == self.stock:
            self.pos = position
        # print("Position.", "Account:", account, "Symbol:", contract.symbol, "SecType:",
        #       contract.secType, "Currency:", contract.currency,
        #       "Position:", position, "Avg cost:", avgCost)


    @iswrapper
    # ! [tickprice]
    def tickPrice(self, reqId: TickerId, tickType: TickType, price: float,
                  attrib: TickAttrib):
        super().tickPrice(reqId, tickType, price, attrib)
        self.price = price
        print("pos: ", self.pos)
        if self.first_buy == False:  # can be fals on first buy or when putting position to zero on last buy!
            if self.message == 'last_buy':
                if self.pos > 0:
                    self.placeOrder(self.nextOrderId(), Contracts.AnyStock(self.stock),
                                    Orders.MarketOrder("SELL", int(self.pos)))
                else:
                    print("pos: ", self.pos)
                    self.placeOrder(self.nextOrderId(), Contracts.AnyStock(self.stock),
                                    Orders.MarketOrder("BUY", int(-1*self.pos)))
                self.done = True
                with open('update.txt', 'w') as file:
                    file.write('')
            else:
                self.placeOrder(self.nextOrderId(), Contracts.AnyStock(self.stock),
                                Orders.MarketOrder("BUY", self.amount/2))
                self.StopPrice = self.price - self.trail
                print("first buy", self.amount/2)
                print("first price: ", self.price)
                self.first_buy = True
        elif self.second_buy == False:
            self.placeOrder(self.nextOrderId(), Contracts.AnyStock(self.stock),
                            Orders.MarketOrder("SELL", self.amount))
            self.second_buy = True

        elif self.pos == self.amount / 2:  # long position
            # print("filled: {}, sold: {}".format(self.filled, self.sold))
            # if self.filled == self.amount and self.sold == False:
            if self.sold == False:  # change position even if there wasn't a full fill
                # print("price {}, stop {}".format(self.price, self.StopPrice))
                if self.price <= self.StopPrice:
                    # self.placeOrder(self.nextOrderId(), Contracts.AnyStock(self.stock),
                    #                 Orders.MarketOrder("SELL", self.amount))

                    # self.StopPrice = self.StopPrice - self.trail
                    print("SELL update stop price: ", self.StopPrice)
                    print('fill: ', self.filled)
                    self.placeOrder(self.nextOrderId(), Contracts.AnyStock(self.stock),
                                    Orders.MarketOrder("SELL", self.filled))
                    # if self.filled < self.amount:
                    #     self.placeOrder(self.nextOrderId(), Contracts.AnyStock(self.stock),
                    #                     Orders.MarketOrder("SELL", self.amount - self.filled))
                    # else:
                    #     self.placeOrder(self.nextOrderId(), Contracts.AnyStock(self.stock),
                    #                     Orders.MarketOrder("SELL", self.amount))
                    #     print("SELL before fill: ", self.amount - self.filled)
                    self.sold = True
                    self.bought = False
                    self.filled = 0
            # seems like I don't need this part now that i dont waiyt for full fill
            elif self.filled == self.amount/2 and self.sold == False:  # second buy
                print("price {}, stop {}".format(self.price, self.StopPrice))
                if self.price <= self.StopPrice:
                    self.placeOrder(self.nextOrderId(), Contracts.AnyStock(self.stock),
                                    Orders.MarketOrder("SELL", self.amount))
                    # self.StopPrice = self.StopPrice - self.trail
                    print("SELL  {} update stop price: {}".format(self.amount, self.StopPrice))

                    self.sold = True
                    self.bought = False
                    self.filled = 0
        elif self.pos == -1 * self.amount / 2:  # short position
            # print("filled: {}, sold: {}".format(self.filled, self.sold))
            # if self.filled == self.amount and self.bought == False:
            if self.bought == False:  # change position even if there wasn't a full fill
                # print("price {}, stop {}".format(self.price, self.StopPrice))
                if self.price >= self.StopPrice:
                    # self.placeOrder(self.nextOrderId(), Contracts.AnyStock(self.stock),
                    #                 Orders.MarketOrder("BUY", self.amount))
                                        # self.StopPrice = self.StopPrice + self.trail
                    print("BUY update stop price: ", self.StopPrice)
                    print('fill: ', self.filled)
                    self.placeOrder(self.nextOrderId(), Contracts.AnyStock(self.stock),
                                    Orders.MarketOrder("BUY", self.filled))
                    # if self.filled < self.amount:
                    #     self.placeOrder(self.nextOrderId(), Contracts.AnyStock(self.stock),
                    #                     Orders.MarketOrder("BUY", self.amount - self.filled))
                    #     print("BUY before fill: ", self.amount - self.filled)
                    # else:
                    #     self.placeOrder(self.nextOrderId(), Contracts.AnyStock(self.stock),
                    #                     Orders.MarketOrder("BUY", self.amount))
                    self.sold = False
                    self.bought = True
                    self.filled = 0
        # elif self.pos == 0:
        #     print('second buy: ', self.second_buy)
        #     if self.second_buy == False:
        #         print('second buy SELL : ', self.amount / 2)
        #         self.placeOrder(self.nextOrderId(), Contracts.AnyStock(self.stock),
        #                         Orders.MarketOrder("SELL", 100))
        #         self.second_buy = True


        current_time = dt.datetime.now()
        timepast = current_time - self.start_time
        # print("seconds: ", timepast.seconds/60)
        if timepast.seconds/60 > float(self.delta):
            self.start_time = dt.datetime.now()
            if self.pos >= 0:
                print("filled: ", self.filled)
                self.StopPrice = self.price - self.trail
                print("##############################################Time driven update stop price: ", self.StopPrice)
            else:
                self.StopPrice = self.price + self.trail
                print("##############################################Time driven update stop price: ", self.StopPrice)

        try:
            with open('update.txt', 'r') as file:
                self.message = file.read()

            # message = self.gui_queue.get_nowait()  # see if something has been posted to Queue
            # message = self.gui_queue.get()
            # print("*************************message**************************: {}", message)
            if self.message == 'update':
                if self.pos >= 0:
                    self.StopPrice = self.price - self.trail
                    print("MANUALE update stop price: ", self.StopPrice)
                else:
                    self.StopPrice = self.price + self.trail
                    print("MANUALE update stop price: ", self.StopPrice)
                with open('update.txt', 'w') as file:
                    file.write('')
            elif self.message == 'last_buy':
                self.first_buy = False

        except:  # get_nowait() will get exception when Queue is empty
            pass
            # print("no message")  # message = None  # nothing in queue so do nothing

        self.priceList.append(price)
        # print("price list: ", self.priceList)


    @iswrapper
    # ! [ticksize]
    def tickSize(self, reqId: TickerId, tickType: TickType, size: int):
        super().tickSize(reqId, tickType, size)
        # print("TickSize. TickerId:", reqId, "TickType:", tickType, "Size:", size)
    # ! [ticksize]

    @iswrapper
    # ! [tickgeneric]
    def tickGeneric(self, reqId: TickerId, tickType: TickType, value: float):
        super().tickGeneric(reqId, tickType, value)
        # print("TickGeneric. TickerId:", reqId, "TickType:", tickType, "Value:", value)
    # ! [tickgeneric]

    @iswrapper
    # ! [tickstring]
    def tickString(self, reqId: TickerId, tickType: TickType, value: str):
        super().tickString(reqId, tickType, value)
        # print("TickString. TickerId:", reqId, "Type:", tickType, "Value:", value)
    # ! [tickstring]

    @iswrapper
    # ! [ticksnapshotend]
    def tickSnapshotEnd(self, reqId: int):
        super().tickSnapshotEnd(reqId)
        # print("TickSnapshotEnd. TickerId:", reqId)
    # ! [ticksnapshotend]

    @iswrapper
    # ! [rerouteMktDataReq]
    def rerouteMktDataReq(self, reqId: int, conId: int, exchange: str):
        super().rerouteMktDataReq(reqId, conId, exchange)
        print("Re-route market data request. ReqId:", reqId, "ConId:", conId, "Exchange:", exchange)
    # ! [rerouteMktDataReq]

    @iswrapper
    # ! [marketRule]
    def marketRule(self, marketRuleId: int, priceIncrements: ListOfPriceIncrements):
        super().marketRule(marketRuleId, priceIncrements)
        print("Market Rule ID: ", marketRuleId)
        for priceIncrement in priceIncrements:
            print("Price Increment.", priceIncrement)
    # ! [marketRule]

    @printWhenExecuting
    def tickByTickOperations_req(self):
        # Requesting tick-by-tick data (only refresh)
        # ! [reqtickbytick]
        self.reqTickByTickData(19001, ContractSamples.EuropeanStock2(), "Last", 0, True)
        self.reqTickByTickData(19002, ContractSamples.EuropeanStock2(), "AllLast", 0, False)
        self.reqTickByTickData(19003, ContractSamples.EuropeanStock2(), "BidAsk", 0, True)
        self.reqTickByTickData(19004, ContractSamples.EurGbpFx(), "MidPoint", 0, False)
        # ! [reqtickbytick]

        # Requesting tick-by-tick data (refresh + historicalticks)
        # ! [reqtickbytickwithhist]
        self.reqTickByTickData(19005, ContractSamples.EuropeanStock2(), "Last", 10, False)
        self.reqTickByTickData(19006, ContractSamples.EuropeanStock2(), "AllLast", 10, False)
        self.reqTickByTickData(19007, ContractSamples.EuropeanStock2(), "BidAsk", 10, False)
        self.reqTickByTickData(19008, ContractSamples.EurGbpFx(), "MidPoint", 10, True)
        # ! [reqtickbytickwithhist]

    @printWhenExecuting
    def tickByTickOperations_cancel(self):
        # ! [canceltickbytick]
        self.cancelTickByTickData(19001)
        self.cancelTickByTickData(19002)
        self.cancelTickByTickData(19003)
        self.cancelTickByTickData(19004)
        # ! [canceltickbytick]

        # ! [canceltickbytickwithhist]
        self.cancelTickByTickData(19005)
        self.cancelTickByTickData(19006)
        self.cancelTickByTickData(19007)
        self.cancelTickByTickData(19008)
        # ! [canceltickbytickwithhist]
        
    @iswrapper
    # ! [orderbound]
    def orderBound(self, orderId: int, apiClientId: int, apiOrderId: int):
        super().orderBound(orderId, apiClientId, apiOrderId)
        print("OrderBound.", "OrderId:", orderId, "ApiClientId:", apiClientId, "ApiOrderId:", apiOrderId)
    # ! [orderbound]

    @iswrapper
    # ! [tickbytickalllast]
    def tickByTickAllLast(self, reqId: int, tickType: int, time: int, price: float,
                          size: int, tickAtrribLast: TickAttribLast, exchange: str,
                          specialConditions: str):
        super().tickByTickAllLast(reqId, tickType, time, price, size, tickAtrribLast,
                                  exchange, specialConditions)
        if tickType == 1:
            print("Last.", end='')
        else:
            print("AllLast.", end='')
        # print(" ReqId:", reqId,
        #       "Time:", datetime.datetime.fromtimestamp(time).strftime("%Y%m%d %H:%M:%S"),
        #       "Price:", price, "Size:", size, "Exch:" , exchange,
        #       "Spec Cond:", specialConditions, "PastLimit:", tickAtrribLast.pastLimit, "Unreported:", tickAtrribLast.unreported)
    # ! [tickbytickalllast]

    @iswrapper
    # ! [tickbytickbidask]
    def tickByTickBidAsk(self, reqId: int, time: int, bidPrice: float, askPrice: float,
                         bidSize: int, askSize: int, tickAttribBidAsk: TickAttribBidAsk):
        super().tickByTickBidAsk(reqId, time, bidPrice, askPrice, bidSize,
                                 askSize, tickAttribBidAsk)
        # print("BidAsk. ReqId:", reqId,
        #       "Time:", datetime.datetime.fromtimestamp(time).strftime("%Y%m%d %H:%M:%S"),
        #       "BidPrice:", bidPrice, "AskPrice:", askPrice, "BidSize:", bidSize,
        #       "AskSize:", askSize, "BidPastLow:", tickAttribBidAsk.bidPastLow, "AskPastHigh:", tickAttribBidAsk.askPastHigh)
    # ! [tickbytickbidask]

    # ! [tickbytickmidpoint]
    @iswrapper
    def tickByTickMidPoint(self, reqId: int, time: int, midPoint: float):
        super().tickByTickMidPoint(reqId, time, midPoint)
        # print("Midpoint. ReqId:", reqId,
        #       "Time:", datetime.datetime.fromtimestamp(time).strftime("%Y%m%d %H:%M:%S"),
        #       "MidPoint:", midPoint)
    # ! [tickbytickmidpoint]

    @printWhenExecuting
    def contractOperations(self):
        # ! [reqcontractdetails]
        self.reqContractDetails(210, ContractSamples.OptionForQuery())
        self.reqContractDetails(211, ContractSamples.EurGbpFx())
        self.reqContractDetails(212, ContractSamples.Bond())
        self.reqContractDetails(213, ContractSamples.FuturesOnOptions())
        self.reqContractDetails(214, ContractSamples.SimpleFuture())
        # ! [reqcontractdetails]

        # ! [reqmatchingsymbols]
        self.reqMatchingSymbols(211, "IB")
        # ! [reqmatchingsymbols]

    @iswrapper
    # ! [contractdetails]
    def contractDetails(self, reqId: int, contractDetails: ContractDetails):
        super().contractDetails(reqId, contractDetails)
        printinstance(contractDetails)
    # ! [contractdetails]

    @iswrapper
    # ! [bondcontractdetails]
    def bondContractDetails(self, reqId: int, contractDetails: ContractDetails):
        super().bondContractDetails(reqId, contractDetails)
        printinstance(contractDetails)
    # ! [bondcontractdetails]

    @iswrapper
    # ! [contractdetailsend]
    def contractDetailsEnd(self, reqId: int):
        super().contractDetailsEnd(reqId)
        print("ContractDetailsEnd. ReqId:", reqId)
    # ! [contractdetailsend]

    @iswrapper
    # ! [symbolSamples]
    def symbolSamples(self, reqId: int,
                      contractDescriptions: ListOfContractDescription):
        super().symbolSamples(reqId, contractDescriptions)
        print("Symbol Samples. Request Id: ", reqId)

        for contractDescription in contractDescriptions:
            derivSecTypes = ""
            for derivSecType in contractDescription.derivativeSecTypes:
                derivSecTypes += derivSecType
                derivSecTypes += " "
            print("Contract: conId:%s, symbol:%s, secType:%s primExchange:%s, "
                  "currency:%s, derivativeSecTypes:%s" % (
                contractDescription.contract.conId,
                contractDescription.contract.symbol,
                contractDescription.contract.secType,
                contractDescription.contract.primaryExchange,
                contractDescription.contract.currency, derivSecTypes))
    # ! [symbolSamples]


    @iswrapper
    # ! [smartcomponents]
    def smartComponents(self, reqId:int, smartComponentMap:SmartComponentMap):
        super().smartComponents(reqId, smartComponentMap)
        print("SmartComponents:")
        for smartComponent in smartComponentMap:
            print("SmartComponent.", smartComponent)
    # ! [smartcomponents]

    @iswrapper
    # ! [tickReqParams]
    def tickReqParams(self, tickerId:int, minTick:float,
                      bboExchange:str, snapshotPermissions:int):
        super().tickReqParams(tickerId, minTick, bboExchange, snapshotPermissions)
        print("TickReqParams. TickerId:", tickerId, "MinTick:", minTick,
              "BboExchange:", bboExchange, "SnapshotPermissions:", snapshotPermissions)
    # ! [tickReqParams]

    def bracketSample(self, action, amount, price, trail):
        # BRACKET ORDER
        # !
        bracket = Orders.NewBracketOrder(self.nextOrderId(), action, amount, price, trail)
        # bracket = Orders.BracketOrder(self.nextOrderId(), "BUY", 100, 228.5, 229, 228.2)
        for o in bracket:
            self.placeOrder(o.orderId, Contracts.TQQQstock(), o)
            self.nextOrderId()  # need to advance this we'll skip one extra oid, it's fine
            # ! [bracketsubmit]
        # return price, trail


    @printWhenExecuting
    def whatIfOrderOperations(self):
    # ! [whatiflimitorder]
        whatIfOrder = OrderSamples.LimitOrder("SELL", 5, 70)
        whatIfOrder.whatIf = True
        self.placeOrder(self.nextOrderId(), ContractSamples.USStockAtSmart(), whatIfOrder)
    # ! [whatiflimitorder]
        time.sleep(2)

    @printWhenExecuting
    def orderOperations_req(self):
        self.reqIds(-1)

        # self.placeOrder(self.nextOrderId(), Contracts.TQQQstock(),
        #                 Orders.MarketOrder("BUY", 100))
        # self.placeOrder(self.nextOrderId(), Contracts.TQQQstock(),
        #                 Orders.NewTrailingStop("SELL", 200, 0.01, 0))


        # self.bracketSample()

        self.tickDataOperations_req()


    @iswrapper
    # ! [execdetails]
    def execDetails(self, reqId: int, contract: Contract, execution: Execution):
        super().execDetails(reqId, contract, execution)
        # print("ExecDetails. ReqId:", reqId, "Symbol:", contract.symbol, "SecType:", contract.secType, "Currency:", contract.currency, execution)
    # ! [execdetails]

    @iswrapper
    # ! [execdetailsend]
    def execDetailsEnd(self, reqId: int):
        super().execDetailsEnd(reqId)
        # print("ExecDetailsEnd. ReqId:", reqId)
    # ! [execdetailsend]

    @iswrapper
    # ! [commissionreport]
    def commissionReport(self, commissionReport: CommissionReport):
        super().commissionReport(commissionReport)
        # print("CommissionReport.", commissionReport)
    # ! [commissionreport]

    @iswrapper
    # ! [currenttime]
    def currentTime(self, time:int):
        super().currentTime(time)
        print("CurrentTime:", datetime.datetime.fromtimestamp(time).strftime("%Y%m%d %H:%M:%S"))
    # ! [currenttime]

    @iswrapper
    # ! [completedorder]
    def completedOrder(self, contract: Contract, order: Order,
                  orderState: OrderState):
        super().completedOrder(contract, order, orderState)
        print("#####################################################")
        print("AuxPrice:", order.auxPrice)
        # print("CompletedOrder. PermId:", order.permId, "ParentPermId:", utils.longToStr(order.parentPermId), "Account:", order.account,
        #       "Symbol:", contract.symbol, "SecType:", contract.secType, "Exchange:", contract.exchange,
        #       "Action:", order.action, "OrderType:", order.orderType, "TotalQty:", order.totalQuantity,
        #       "CashQty:", order.cashQty, "FilledQty:", order.filledQuantity,
        #       "LmtPrice:", order.lmtPrice, "AuxPrice:", order.auxPrice, "Status:", orderState.status,
        #       "Completed time:", orderState.completedTime, "Completed Status:" + orderState.completedStatus)
    # ! [completedorder]

    @iswrapper
    # ! [completedordersend]
    def completedOrdersEnd(self):
        super().completedOrdersEnd()
        print("CompletedOrdersEnd")
    # ! [completedordersend]


def main():
    SetupLogger()
    logging.debug("now is %s", datetime.datetime.now())
    logging.getLogger().setLevel(logging.ERROR)

    cmdLineParser = argparse.ArgumentParser("api tests")
    # cmdLineParser.add_option("-c", action="store_True", dest="use_cache", default = False, help = "use the cache")
    # cmdLineParser.add_option("-f", action="store", type="string", dest="file", default="", help="the input file")
    cmdLineParser.add_argument("-p", "--port", action="store", type=int,
                               dest="port", default=7497, help="The TCP port to use")
    cmdLineParser.add_argument("-C", "--global-cancel", action="store_true",
                               dest="global_cancel", default=False,
                               help="whether to trigger a globalCancel req")
    args = cmdLineParser.parse_args()
    print("Using args", args)
    logging.debug("Using args %s", args)
    # print(args)


    # enable logging when member vars are assigned
    from ibapi import utils
    Order.__setattr__ = utils.setattr_log
    Contract.__setattr__ = utils.setattr_log
    DeltaNeutralContract.__setattr__ = utils.setattr_log
    TagValue.__setattr__ = utils.setattr_log
    TimeCondition.__setattr__ = utils.setattr_log
    ExecutionCondition.__setattr__ = utils.setattr_log
    MarginCondition.__setattr__ = utils.setattr_log
    PriceCondition.__setattr__ = utils.setattr_log
    PercentChangeCondition.__setattr__ = utils.setattr_log
    VolumeCondition.__setattr__ = utils.setattr_log

    # from inspect import signature as sig
    # import code code.interact(local=dict(globals(), **locals()))
    # sys.exit(1)

    # tc = TestClient(None)
    # tc.reqMktData(1101, ContractSamples.USStockAtSmart(), "", False, None)
    # print(tc.reqId2nReq)
    # sys.exit(1)

    try:
        app = TestApp()
        if args.global_cancel:
            app.globalCancelOnly = True
        # ! [connect]
        app.connect("127.0.0.1", args.port, clientId=0)
        # ! [connect]
        print("serverVersion:%s connectionTime:%s" % (app.serverVersion(),
                                                      app.twsConnectionTime()))

        # ! [clientrun]
        app.run()
        # ! [clientrun]
    except:
        raise
    finally:
        app.dumpTestCoverageSituation()
        app.dumpReqAnsErrSituation()


if __name__ == "__main__":
    main()

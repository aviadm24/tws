"""
Copyright (C) 2019 Interactive Brokers LLC. All rights reserved. This code is subject to the terms
 and conditions of the IB API Non-Commercial License or the IB API Commercial License, as applicable.
"""
# https://algotrading101.com/learn/interactive-brokers-python-api-native-guide/

import argparse
import datetime
import collections
import logging
from ibapi.utils import iswrapper

# types
from ibapi.common import *  # @UnusedWildImport
from ibapi.order_condition import *  # @UnusedWildImport
from ibapi.contract import *  # @UnusedWildImport
from ibapi.order import *  # @UnusedWildImport
from ibapi.order_state import *  # @UnusedWildImport
from ibapi.execution import Execution
from ibapi.ticktype import *  # @UnusedWildImport
from ibapi.tag_value import TagValue
from Contracts import Contracts
from Orders import Orders
from tws_algos import AvailableAlgoParams
import datetime as dt
from base_config import SetupLogger, printWhenExecuting, TestClient, TestWrapper
RUNTIME = 10


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
        self.start_price = 0
        self.priceList = []
        self.delta = delta
        self.start_time = start_time
        self.stock_dir = 'up'
        self.pos = 0
        self.StopPrice = 0
        self.filled = 0
        self.mktCapPrice = 0
        self.sellOrder = False
        self.buyOrder = False
        self.buyOrSell = False
        self.sellTrailOn = False
        self.buyTrailOn = False
        self.gui_queue = gui_queue

        self.stock = stock
        self.trail = trail
        self.amount = amount
        self.nextSellingPrice = 0
        self.id = 0
        self.status = ''
        self.message = ''
        self.first_buy = True
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
    def connectAck(self):
        if self.asynchronous:
            self.startApi()

    @iswrapper
    def nextValidId(self, orderId: int):
        super().nextValidId(orderId)
        logging.debug("setting nextValidOrderId: %d", orderId)
        self.nextValidOrderId = orderId
        print("NextValidId:", orderId)
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
            # self.reqGlobalCancel()
            # self.marketDataTypeOperations()
            self.accountOperations_req()
            # self.tickDataOperations_req()
            # self.marketDepthOperations_req()
            # self.realTimeBarsOperations_req()
            self.orderOperations_req()
            # self.tickByTickOperations_req()

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
        self.orderOperations_cancel()
        # self.accountOperations_cancel()
        self.tickDataOperations_cancel()
        # self.marketDepthOperations_cancel()
        # self.realTimeBarsOperations_cancel()
        # self.historicalDataOperations_cancel()
        # self.optionsOperations_cancel()
        # self.marketScanners_cancel()
        # self.fundamentalsOperations_cancel()
        # self.bulletinsOperations_cancel()
        # self.newsOperations_cancel()
        # self.pnlOperations_cancel()
        # self.histogramOperations_cancel()
        # self.continuousFuturesOperations_cancel()
        self.tickByTickOperations_cancel()
        print("Executing cancels ... finished")

    def nextOrderId(self):
        oid = self.nextValidOrderId
        self.nextValidOrderId += 1
        return oid

    @iswrapper
    def error(self, reqId: TickerId, errorCode: int, errorString: str):
        super().error(reqId, errorCode, errorString)
        print("Error. Id:", reqId, "Code:", errorCode, "Msg:", errorString)
    # ! [error] self.reqId2nErr[reqId] += 1

    @iswrapper
    def winError(self, text: str, lastError: int):
        super().winError(text, lastError)

    @iswrapper
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
    def openOrderEnd(self):
        super().openOrderEnd()
        # print("OpenOrderEnd")

        logging.debug("Received %d openOrders", len(self.permId2ord))

    # ! [openorderend]

    @iswrapper
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
    def tickPrice(self, reqId: TickerId, tickType: TickType, price: float,
                  attrib: TickAttrib):
        super().tickPrice(reqId, tickType, price, attrib)
        # AvailableAlgoParams.FillAdaptiveParams(baseOrder, "Urgent")
        self.price = price
        self.priceList.append(price)
        # print("pos: ", self.pos)

        if self.stock == "ULVR":
            contract = Contracts.ULVR()
        else:
            contract = Contracts.QQQ()
        if self.first_buy:
            self.start_price = price
            self.placeOrder(self.nextOrderId(), contract,
                            Orders.MarketOrder("BUY", 100))
            # reguler stop
            self.placeOrder(self.nextOrderId(), contract, Orders.Stop("SELL", self.amount, self.start_price-0.01))
            self.first_buy = False
            self.sellOrder = True
            print("first buy: ", price)

        elif price > self.start_price + 0.01 and not self.sellOrder and not self.sellTrailOn:
            self.placeOrder(self.nextOrderId(), contract, Orders.Stop("SELL", self.amount, self.start_price - 0.01))
            self.sellOrder = True
            self.buyTrailOn = False
            print("price above start price: ", price)

        elif price - self.start_price > self.trail and not self.sellOrder:
            self.reqGlobalCancel()
            print("cancle stop sell")
            self.placeOrder(self.nextOrderId(), contract, Orders.NewTrailingStop("SELL", self.amount, self.start_price,
                            self.start_price - self.trail))
            self.sellOrder = True
            self.sellTrailOn = True
            print("price above start price+trail: ", price)

        elif price < self.start_price - 0.01 and self.sellOrder and not self.buyTrailOn:
            self.placeOrder(self.nextOrderId(), contract, Orders.Stop("BUY", self.amount, self.start_price + 0.01))
            self.sellOrder = False
            self.sellTrailOn = False
            print("price under start price: ", price)

        elif price < self.start_price - self.trail and self.sellOrder:
            self.reqGlobalCancel()
            print("cancle stop buy")
            self.placeOrder(self.nextOrderId(), contract, Orders.NewTrailingStop("BUY", self.amount, self.start_price,
                            self.start_price - self.trail))
            self.sellOrder = False
            print("price under start price-trail: ", price)





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
    def orderOperations_req(self):
        self.reqIds(-1)

        self.tickDataOperations_req()

    @printWhenExecuting
    def tickDataOperations_req(self):
        self.reqMarketDataType(MarketDataTypeEnum.DELAYED_FROZEN)
        print("stock symbol: ", self.stock)
        self.reqMktData(1000, Contracts.AnyStock(self.stock), "", False, False, [])

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

    try:
        app = TestApp()
        if args.global_cancel:
            app.globalCancelOnly = True
        app.connect("127.0.0.1", args.port, clientId=0)
        # print("serverVersion:%s connectionTime:%s" % (app.serverVersion(),
        #                                               app.twsConnectionTime()))
        app.run()

    except:
        raise
    finally:
        app.dumpTestCoverageSituation()
        app.dumpReqAnsErrSituation()


if __name__ == "__main__":
    main()

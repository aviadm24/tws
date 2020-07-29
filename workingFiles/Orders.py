from ibapi.order import (OrderComboLeg, Order)
from ibapi.common import *  # @UnusedWildImport
from ibapi.tag_value import TagValue
from ibapi import order_condition
from ibapi.order_condition import *  # @UnusedWildImport


class Orders:

    @staticmethod
    def MarketOrder(action: str, quantity: float):
        # ! [market]
        order = Order()
        order.action = action
        order.orderType = "MKT"
        order.totalQuantity = quantity
        # ! [market]
        return order

    @staticmethod
    def Stop(action: str, quantity: float, stopPrice: float):
        # ! [stop]
        order = Order()
        order.action = action
        order.orderType = "STP"
        order.auxPrice = stopPrice
        order.totalQuantity = quantity
        # ! [stop]
        return order

    @staticmethod
    def TrailingStop(action:str, quantity:float, trailingPercent:float,
                     trailStopPrice:float):

        # ! [trailingstop]
        order = Order()
        order.action = action
        order.orderType = "TRAIL"
        order.totalQuantity = quantity
        order.trailingPercent = trailingPercent
        order.trailStopPrice = trailStopPrice
        # ! [trailingstop]
        return order

    @staticmethod
    def NewTrailingStop (action:str, quantity:float, auxPrice:float,
                     trailStopPrice:float):

        # ! [trailingstop]
        order = Order()
        order.action = action
        order.orderType = "TRAIL"
        order.totalQuantity = quantity
        # order.trailingPercent = trailingPercent
        order.auxPrice = auxPrice
        order.trailStopPrice = trailStopPrice
        # ! [trailingstop]
        return order

    """ <summary>
    #/ Bracket orders are designed to help limit your loss and lock in a profit by "bracketing" an order with two opposite-side orders.
    #/ A BUY order is bracketed by a high-side sell limit order and a low-side sell stop order. A SELL order is bracketed by a high-side buy
    #/ stop order and a low side buy limit order.
    #/ Products: CFD, BAG, FOP, CASH, FUT, OPT, STK, WAR
    </summary>"""


    # ! [bracket]
    @staticmethod
    def BracketOrder(parentOrderId: int, action: str, quantity: float,
                     limitPrice: float, takeProfitLimitPrice: float,
                     stopLossPrice: float):
        # This will be our main or "parent" order
        parent = Order()
        parent.orderId = parentOrderId
        parent.action = action
        parent.orderType = "LMT"
        parent.totalQuantity = quantity
        parent.lmtPrice = limitPrice
        # The parent and children orders will need this attribute set to False to prevent accidental executions.
        # The LAST CHILD will have it set to True,
        parent.transmit = False

        takeProfit = Order()
        takeProfit.orderId = parent.orderId + 1
        takeProfit.action = "SELL" if action == "BUY" else "BUY"
        takeProfit.orderType = "LMT"
        takeProfit.totalQuantity = quantity
        takeProfit.lmtPrice = takeProfitLimitPrice
        takeProfit.parentId = parentOrderId
        takeProfit.transmit = False

        stopLoss = Order()
        stopLoss.orderId = parent.orderId + 2
        stopLoss.action = "SELL" if action == "BUY" else "BUY"
        stopLoss.orderType = "STP"
        # Stop trigger price
        stopLoss.auxPrice = stopLossPrice
        stopLoss.totalQuantity = quantity
        stopLoss.parentId = parentOrderId
        # In this case, the low side order will be the last child being sent. Therefore, it needs to set this attribute to True
        # to activate all its predecessors
        stopLoss.transmit = True

        bracketOrder = [parent, takeProfit, stopLoss]
        return bracketOrder

        # ! [bracket]

    # ! [bracket]
    @staticmethod
    def NewBracketOrder(parentOrderId: int, action: str, quantity: float,
                        limitPrice: float, auxPrice: float):
        # This will be our main or "parent" order
        parent = Order()
        parent.orderId = parentOrderId
        parent.action = action
        parent.orderType = "LMT"
        parent.totalQuantity = quantity
        parent.lmtPrice = limitPrice
        # The parent and children orders will need this attribute set to False to prevent accidental executions.
        # The LAST CHILD will have it set to True,
        parent.transmit = False

        turnOver = Order()
        turnOver.orderId = parent.orderId + 1
        turnOver.action = "SELL" if action == "BUY" else "BUY"
        turnOver.orderType = "TRAIL"
        # Stop trigger price
        # turnOver.trailingPercent = trailingPercent
        turnOver.auxPrice = auxPrice
        # turnOver.trailStopPrice = trailStopPrice
        turnOver.totalQuantity = quantity
        turnOver.parentId = parentOrderId
        # In this case, the low side order will be the last child being sent. Therefore, it needs to set this attribute to True
        # to activate all its predecessors
        turnOver.transmit = True

        bracketOrder = [parent, turnOver]
        return bracketOrder

        # ! [bracket]

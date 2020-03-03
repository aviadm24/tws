"""
Copyright (C) 2019 Interactive Brokers LLC. All rights reserved. This code is subject to the terms
 and conditions of the IB API Non-Commercial License or the IB API Commercial License, as applicable.
"""

from ibapi.contract import *  # @UnusedWildImport


class Contracts:

    @staticmethod
    def USStock():
        # ! [stkcontract]
        contract = Contract()
        contract.symbol = "IBKR"
        contract.secType = "STK"
        contract.currency = "USD"
        # In the API side, NASDAQ is always defined as ISLAND in the exchange field
        contract.exchange = "ISLAND"
        # ! [stkcontract]
        return contract

    @staticmethod
    def USStockWithPrimaryExch():
        # ! [stkcontractwithprimary]
        contract = Contract()
        contract.symbol = "MSFT"
        contract.secType = "STK"
        contract.currency = "USD"
        contract.exchange = "SMART"
        # Specify the Primary Exchange attribute to avoid contract ambiguity
        # (there is an ambiguity because there is also a MSFT contract with primary exchange = "AEB")
        contract.primaryExchange = "ISLAND"
        # ! [stkcontractwithprimary]
        return contract

    @staticmethod
    def TQQQstock():
        contract = Contract()
        contract.symbol = "QQQ"
        contract.secType = "STK"
        contract.currency = "USD"
        contract.exchange = "SMART"
        return contract

    @staticmethod
    def AnyStock(stock):
        contract = Contract()
        contract.symbol = stock
        contract.secType = "STK"
        contract.currency = "USD"
        contract.exchange = "SMART"
        return contract

def Test():
    from ibapi.utils import ExerciseStaticMethods
    ExerciseStaticMethods(ContractSamples)


if "__main__" == __name__:
    Test()


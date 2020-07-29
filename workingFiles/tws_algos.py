from ibapi.object_implem import Object
from ibapi.tag_value import TagValue
from ibapi.order import Order


class AvailableAlgoParams(Object):

    @staticmethod
    def FillAdaptiveParams(baseOrder: Order, priority: str):
        baseOrder.algoStrategy = "Adaptive"
        baseOrder.algoParams = []
        baseOrder.algoParams.append(TagValue("adaptivePriority", priority))

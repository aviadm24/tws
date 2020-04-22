import PySimpleGUI as sg
import json
import datetime as dt
import os
import threading
import queue
import traceback
import argparse
import datetime
import collections
import inspect

import logging
import time
import os.path

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

from Contracts import Contracts
from Orders import Orders
from Program2 import TestApp

# https://github.com/jseparovic/DASTraderScripts

RUNTIME = 10
with open('update.txt', 'w') as file:
    file.write('')


def SetupLogger():
    if not os.path.exists("log"):
        os.makedirs("log")

    time.strftime("pyibapi.%Y%m%d_%H%M%S.log")

    recfmt = '(%(threadName)s) %(asctime)s.%(msecs)03d %(levelname)s %(filename)s:%(lineno)d %(message)s'

    timefmt = '%y%m%d_%H:%M:%S'

    logging.basicConfig(filename=time.strftime("log/pyibapi.%y%m%d_%H%M%S.log"),
                        filemode="w",
                        level=logging.INFO,
                        format=recfmt, datefmt=timefmt)
    logger = logging.getLogger()
    console = logging.StreamHandler()
    console.setLevel(logging.ERROR)
    logger.addHandler(console)


def main(stock, trail, amount, delta, start_time, gui_queue):
    SetupLogger()
    logging.debug("now is %s", datetime.datetime.now())
    logging.getLogger().setLevel(logging.ERROR)

    cmdLineParser = argparse.ArgumentParser("api tests")
    cmdLineParser.add_argument("-p", "--port", action="store", type=int,
                               dest="port", default=7497, help="The TCP port to use")
    cmdLineParser.add_argument("-C", "--global-cancel", action="store_true",
                               dest="global_cancel", default=False,
                               help="whether to trigger a globalCancel req")
    args = cmdLineParser.parse_args()
    # print("Using args", args)
    logging.debug("Using args %s", args)
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
        app = TestApp(stock, trail, amount, delta, start_time, gui_queue)
        if args.global_cancel:
            app.globalCancelOnly = True
        # ! [connect]
        app.connect("127.0.0.1", args.port, clientId=0)
        # ! [connect]
        # print("serverVersion:%s connectionTime:%s" % (app.serverVersion(),
        #                                               app.twsConnectionTime()))

        # ! [clientrun]
        app.run()
        # ! [clientrun]
    except:
        raise
    finally:
        app.dumpTestCoverageSituation()
        app.dumpReqAnsErrSituation()
    return app


sg.change_look_and_feel('DarkAmber')	# Add a touch of color
# All the stuff inside your window.
# element.Widget = remi.gui.Slider(layout_orientation = remi.gui.Widget.LAYOUT_HORIZONTAL, default_value=element.DefaultValue, min=element.Range[0], max=element.Range[1],step=element.Resolution)
layout = [
            [sg.Text('Yosef TWS GUI')],
            [sg.Text('Platform'), sg.Checkbox('TWS', key='tws', default=True)],
            [sg.Input('TQQQ', size=(20, 1), key='stock'),
             sg.Frame('Trail - Amount', [[
                 sg.Slider(range=(0.01, 0.05), resolution=0.01, orientation='v', size=(5, 20), default_value=0.02, key='trail'),
                 sg.Slider(range=(100, 1000), resolution=100, orientation='v', size=(5, 20), default_value=200, key='amount'),
                 ]])],
            [sg.Text('Enter delta time in minutes'), sg.Input('1', key='delta')],
            [sg.Button('Start')],
            [sg.Button('Update Stop'), sg.Button('Position zero')],
            [sg.ProgressBar(1, orientation='h', size=(20, 20), key='progress')],
            [sg.Button('Cancel')]
         ]

window = sg.Window('', layout)
progress_bar = window['progress']
while True:
    event, values = window.read()

    # print('events: ', event)
    # print('vals: ', values)
    gui_queue = queue.Queue()
    if event == 'Start':
        stock, trail, amount, delta = values['stock'], values['trail'], values['amount'], values['delta']
        start_time = dt.datetime.now()
        #  https://github.com/PySimpleGUI/PySimpleGUI/blob/master/DemoPrograms/Demo_Multithreaded_Multiple_Threads.py
        thread_id = threading.Thread(
            target=main,
            args=(stock, trail, amount, delta, start_time, gui_queue),
            daemon=True)
        app = thread_id.start()

        print(stock, trail, amount)
        # main(stock, trail, amount)
    if event == 'Update Stop':
        with open('update.txt', 'w') as file:
            file.write('update')
        # gui_queue.put('update2')
        # print("queue: ", gui_queue.get())
    if event == 'Position zero':
        with open('update.txt', 'w') as file:
            file.write('last_buy')
    if event in (None, 'Cancel'):  # if user closes window or clicks cancel
        try:
            #  https: // stackoverflow.com / questions / 42867933 / ib - api - python - sample -not -using - ibpy
            app.done = True
        except:
            pass
        finally:
            break
    # current_time = dt.datetime.now()
    # timepast = current_time - self.start_time
    # if timepast.seconds > 10:
    #     print('--------------------------------{} past -------------------------------------------------'.
    #           format(timepast.seconds))
    #     app.done = True


window.close()
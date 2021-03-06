import queue
import threading
import time
import PySimpleGUI as sg

"""
    You want to look for 3 points in this code, marked with comment "LOCATION X".
    1. Where you put your call that takes a long time
    2. Where the trigger to make the call takes place in the event loop
    3. Where the completion of the call is indicated in the event loop
    Demo on how to add a long-running item to your PySimpleGUI Event Loop
    If you want to do something that takes a long time, and you do it in the
    main event loop, you'll quickly begin to see messages from windows that your
    program has hung, asking if you want to kill it.

    The problem is not that your problem is hung, the problem is that you are
    not calling Read or Refresh often enough.

    One way through this, shown here, is to put your long work into a thread that
    is spun off, allowed to work, and then gets back to the GUI when it's done working
    on that task.

    Every time you start up one of these long-running functions, you'll give it an "ID".
    When the function completes, it will send to the GUI Event Loop a message with
    the format:
        work_id ::: done
    This makes it easy to parse out your original work ID

    You can hard code these IDs to make your code more readable.  For example, maybe
    you have a function named "update_user_list()".  You can call the work ID "user list".
    Then check for the message coming back later from the work task to see if it starts
    with "user list".  If so, then that long-running task is over.

"""


# ############################# User callable CPU intensive code #############################
# Put your long running code inside this "wrapper"
# NEVER make calls to PySimpleGUI from this thread (or any thread)!
# Create one of these functions for EVERY long-running call you want to make


def long_function_wrapper(gui_queue):
    while True:
        time.sleep(1)
        try:
            message = gui_queue.get_nowait()
            print("message: ", message)
            if message == "stop":
                gui_queue.put("ok")
        except:
            print("empty")

    return


############################# Begin GUI code #############################
def the_gui():
    sg.change_look_and_feel('Light Brown 3')

    # queue used to communicate between the gui and long-running code
    gui_queue = queue.Queue()

    layout = [[sg.Text('Multithreaded Work Example')],
              [sg.Text('Click Go to start a long-running function call')],
              [sg.Text(size=(25, 1), key='-OUTPUT-')],
              [sg.Text(size=(25, 1), key='-OUTPUT2-')],
              [sg.Text('⚫', text_color='blue', key=i, pad=(0, 0), font='Default 14') for i in range(20)],
              [sg.Button('Go'), sg.Button('Popup'), sg.Button('check'), sg.Button('Exit')], ]

    window = sg.Window('Multithreaded Window', layout)
    # --------------------- EVENT LOOP ---------------------
    work_id = 0
    while True:
        # wait for up to 100 ms for a GUI event
        event, values = window.read(timeout=100)
        if event in (None, 'Exit'):
            break
        if event == 'Go':  # clicking "Go" starts a long running work item by starting thread
            window['-OUTPUT-'].update('Starting long work %s' % work_id)
            window[work_id].update(text_color='red')
            # LOCATION 2
            # STARTING long run by starting a thread
            thread_id = threading.Thread(
                target=long_function_wrapper,
                args=(gui_queue,),
                daemon=True)
            thread_id.start()
            work_id = work_id + 1 if work_id < 19 else 0
        # --------------- Read next message coming in from threads ---------------


        if event == 'Popup':
            gui_queue.put('stop')
        if event == 'check':
            try:
                message = gui_queue.get_nowait()
                print("got back: ", message)
                # at this point, the thread exits
            except queue.Empty:  # get_nowait() will get exception when Queue is empty
                message = None  # nothing in queue so do nothing

            # if message received from queue, then some work was completed
            if message is not None:
                window['-OUTPUT2-'].update(
                    'Complete Work ID ')

    # if user exits the window, then close the window and exit the GUI func
    window.close()


############################# Main #############################


if __name__ == '__main__':
    the_gui()
    print('Exiting Program')
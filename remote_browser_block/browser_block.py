# mstsc - שליטה מרחוק
# https://superuser.com/questions/1113796/how-to-run-a-python-script-with-cmd-exe-and-make-it-invisible
# https://www.winhelponline.com/blog/run-bat-files-invisibly-without-displaying-command-prompt/
# use this command - nircmd exec hide [path to batch file]
# https://www.nirsoft.net/utils/nircmd.html
import sched, time
import psutil
s = sched.scheduler(time.time, time.sleep)


def do_something(sc):
    print("function check")
    for proc in psutil.process_iter():
        # print(proc.name())
        # check whether the process name matches
        if proc.name() == "MicrosoftEdge.exe":
            proc.kill()
    s.enter(1, 1, do_something, (sc,))

s.enter(1, 1, do_something, (s,))
s.run()




import psutil
for num, proc in enumerate(psutil.process_iter()):
    print(num, ' - ', proc.name())
    # check whether the process name matches
    if proc.name() == "python.exe":
        proc.kill()
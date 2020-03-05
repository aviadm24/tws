import datetime as dt
import time
start_time = dt.datetime.now()
time.sleep(5)
current_time = dt.datetime.now()
timepast = current_time - start_time
# if timepast.seconds > 10:
print('--------------------------------{} past -------------------------------------------------'.
      format(timepast.minute))
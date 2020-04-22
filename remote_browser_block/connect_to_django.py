import requests
from datetime import datetime as dt
url = "https://aviad2.herokuapp.com/check_bb"
url2 = "http://127.0.0.1:8000/check_bb"
import time


def post():
    # r = requests.post(url, files=files)
    text = 'time#{}'.format(dt.strftime(dt.now(), '%b %d %Y %I:%M:%S'))
    r = requests.post(url2, data=text.encode('utf-8'))
    print(r.status_code)
    print(r.content)

for i in range(4):
    post()
    time.sleep(10)


# text = dt.strftime(dt.now(), '%b %d %Y %I:%M%p')
# print(text)
# time = dt.strptime(text, '%b %d %Y %I:%M%p')
# print(type(time))
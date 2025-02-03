import hashlib
print("TEST POINT 1")
from urllib.parse import urlencode,unquote
import requests
import json
print("TEST POINT 2")

ADMIN_CREDENTIALS_FILE = "gruzvill_admin.txt"

url_prefix = "https://ibronevik.ru/taxi/c/gruzvill/api/v1/"
bot_admin_login = "admin@ibronevik.ru"
bot_admin_password = "p@ssw0rd"
bot_admin_type = "e-mail"

# make_request осуществляет запросы к апи с автоподстановкой заголовков
def make_request(url, data={}, method="POST"):
    req = None
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json"
    }
    if method == "POST":
        req = requests.post(url, data=urlencode(data), headers=headers)
    elif method == "GET":
        req = requests.get(url, data=urlencode(data), headers=headers)
    data = json.loads(unquote(req.text))
    if req.status_code != 200:
        print("REQUESTS ERROR: " + str(data["code"]))
    return data

# GetAdminHashAndToken получает хэш админа и токен и хранит их в указанном файле(создается если его нет)
# это сделано для сокращения времени запросов, требующих авторизации админа
# token и u_hash не меняются во время работы

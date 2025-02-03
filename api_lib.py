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

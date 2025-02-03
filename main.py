print("TEST POINT")
import datetime
import json

from urllib.parse import urlencode,unquote
import requests
import sys
import asyncio
import time
from threading import Thread

print("Reading config...")
try:
    f = open("config.json", "r")
    f.close()
except:
    raise Exception("config.json not found")

f = open("config.json", "r")
config = json.loads(f.read())
f.close()

LOOP_PERIOD_SECONDS = config["LOOP_PERIOD_SECONDS"]
TAKE_AFTER_SECONDS = config["TAKE_AFTER_SECONDS"]
DRIVER_EMAIL = config["DRIVER_EMAIL"]
WAIT_AFTER_ACCEPT_STATE = config["WAIT_AFTER_ACCEPT_STATE"]
WAIT_AFTER_ARRIVE_STATE = config["WAIT_AFTER_ARRIVE_STATE"]
WAIT_AFTER_START_STATE = config["WAIT_AFTER_START_STATE"]
MULTIUSER_EMAIL = config["MULTIUSER_EMAIL"]

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
def GetAdminHashAndToken():
    try:
        f = open(ADMIN_CREDENTIALS_FILE, "x")
        f.close()
    except:
        pass
    f = open(ADMIN_CREDENTIALS_FILE, "r+")
    r = f.read().split("\n")
    if len(r) == 1 or len(r) == 0:
        data = {
            "login": bot_admin_login,
            "password": bot_admin_password,
            "type": bot_admin_type
        }
        data = make_request(url_prefix + "auth", data)
        AUTH_HASH = data["auth_hash"]
        data = {
            "auth_hash": AUTH_HASH
        }
        data = make_request(url_prefix + "token", data)
        TOKEN = data["data"]["token"]
        U_HASH = data["data"]["u_hash"]
        f.write(TOKEN + "\n" + U_HASH)
        f.close()
        return [TOKEN, U_HASH]
    elif len(r) == 2:
        TOKEN = r[0]
        U_HASH = r[1]
        return [TOKEN, U_HASH]

# Возвращает token и u_hash пользователя, а также данные о пользователе
def GetUserInfo(email:str):
    token_and_hash = GetAdminHashAndToken()
    data = {
        "token": token_and_hash[0],
        "u_hash": token_and_hash[1],
        "u_a_email": email,
    }
    data = make_request(url_prefix + "token", data=data)
    if data["status"] == "error":
        return data
    token = data["data"]["token"]
    u_hash = data["data"]["u_hash"]
    data = make_request(url_prefix + "user", data={
        "token": data["data"]["token"],
        "u_hash": data["data"]["u_hash"]
    })
    data["data"]["token"] = token
    data["data"]["u_hash"] = u_hash
    return data
def RegisterClient(email:str, name):
    token_and_hash = GetAdminHashAndToken()
    data = {
        "token": token_and_hash[0],
        "u_hash": token_and_hash[1],
        "u_name": name,
        "u_email": email,
        "u_role": "2",
        #"ref_code": "test",
        "st": ""
    }
    data = make_request(url_prefix+"register",data=data,method="POST")
    return data
def CreateDrive(u_id,start_latitude,start_longitude,end_latitude,end_longitude,start_datetime,waiting,passenger_count=1,services=[]):
    token,u_hash = GetAdminHashAndToken()
    data = {
        "token": token,
        "u_hash": u_hash,

        "u_a_id":str(u_id), # Авторизован(по токену и хэшу) админ, а drive создастя от лица юзера - имиация пользователя админом
        "u_a_role":1,
        "u_check_state": 2,
        "data":json.dumps({
            "b_start_latitude": start_latitude,
            "b_start_longitude": start_longitude,
            "b_destination_latitude": end_latitude,
            "b_destination_longitude": end_longitude,
            "b_start_datetime": start_datetime,
            "b_max_waiting": waiting,
            "b_passengers_count": passenger_count,
            "b_payment_way": "1",
            "b_services": services
        })

    }
    data = make_request(url_prefix + "drive/", data=data)
    return data

def DrivesList():
    token,u_hash = GetAdminHashAndToken()
    data = {
        "token": token,
        "u_hash": u_hash,

        "u_a_role":2, # user_role=4 for deleting drive under admin
    }
    data = make_request(url_prefix + "drive/now", data=data)
    return data

def OrderLifeCycle(drive, driver):
    order_id = drive["b_id"]
    #1 accept
    data = {
        "token": GetAdminHashAndToken()[0],
        "u_hash": GetAdminHashAndToken()[1],
        "u_a_id": driver["id"],
        "action":"set_performer",
        "performer":1,
        "data": json.dumps({
            "c_id": driver["car_id"],
            "c_payment_way": 1,
            "c_options": {}
        })
    }

    if drive.get("b_voting"):
        codes = [str(x) for x in range(0,11)]
        for i in codes:
            data["b_driver_code"] = i
            res = make_request(url_prefix + "drive/get/" + str(order_id), data=data)
            if res["status"] == "error" and res.get("message","")=="wrong driver code":
                pass
            elif res["status"] == "success":
                break
            else:
                print("VOTING->Accept Error, response: ",json.dumps(res,indent=4))
                exit(1)
    else:
        data = make_request(url_prefix + "drive/get/" + str(order_id), data=data)
    print("API->Accept:",order_id, 'status:', data['status'])


    start_datetime = int(datetime.datetime.fromtimestamp(
        datetime.datetime.strptime(drive["b_start_datetime"], "%Y-%m-%d %H:%M:%S%z").timestamp(), datetime.UTC).timestamp())
    current_time = int(datetime.datetime.now(datetime.UTC).timestamp())

    time.sleep(WAIT_AFTER_ACCEPT_STATE)

    if start_datetime > current_time:
        print("HYBERNATE->Order:",order_id, "for", start_datetime - current_time, "seconds")
        time.sleep(start_datetime - current_time)

    #2 arrive
    data = {
        "token": GetAdminHashAndToken()[0],
        "u_hash": GetAdminHashAndToken()[1],
        "u_a_id": driver["id"],
        "action":"set_arrive_state",
    }
    data = make_request(url_prefix + "drive/get/"+str(order_id), data=data)
    print("API->Arrive:",order_id, 'status:', data)
    time.sleep(WAIT_AFTER_ARRIVE_STATE)
    #3 start
    data = {
        "token": GetAdminHashAndToken()[0],
        "u_hash": GetAdminHashAndToken()[1],
        "u_a_id": driver["id"],
        "action":"set_start_state",
    }
    data = make_request(url_prefix + "drive/get/"+str(order_id), data=data)
    print("API->Start:",order_id, 'status:', data['status'])
    time.sleep(WAIT_AFTER_START_STATE)
    #4 end
    data = {
        "token": GetAdminHashAndToken()[0],
        "u_hash": GetAdminHashAndToken()[1],
        "u_a_id": driver["id"],
        "action":"set_complete_state",
    }
    data = make_request(url_prefix + "drive/get/"+str(order_id), data=data)
    print("API->End:",order_id, 'status:', data['status'])
    pass

async def loop(driver, multiuser):
    drives_list = DrivesList()
    print("ID\tStart\tSecsRemainingForStart\tExpr")
    for i in drives_list["data"]["booking"]:
        drive = drives_list["data"]["booking"][i]

        created_datetime = drive["b_created"]
        max_waiting = drive["b_max_waiting"]
        user_id = drive["u_id"]

        user = make_request(url_prefix + "user/" + str(user_id),{"token": GetAdminHashAndToken()[0],"u_hash": GetAdminHashAndToken()[1]})
        if user["status"] == "error":
            print("User id: " + str(user_id) + " not found")
            continue
        user = user["data"]["user"][str(user_id)]


        created_datetime = int(datetime.datetime.fromtimestamp(datetime.datetime.strptime(created_datetime, "%Y-%m-%d %H:%M:%S%z").timestamp(), datetime.UTC).timestamp())

        current_time = int(datetime.datetime.now(datetime.UTC).timestamp())

        print(str(drive["b_id"]) + "\t" + drive["b_start_datetime"] + "\t" + str(current_time - created_datetime) + "\t" + str(current_time - (created_datetime + TAKE_AFTER_SECONDS)) + "\t" + str(str(user["referrer_u_id"]).lower() + "|" + str(multiuser["u_id"]).lower()))
        if current_time - (created_datetime + TAKE_AFTER_SECONDS) > 0 and str(user["referrer_u_id"]).lower() == str(multiuser["u_id"]).lower() and str(drive["b_state"]) == "1":
            print("Founded suitable drive| id: " + str(drive["b_id"]), "|User id: " + str(user_id), "|Start datetime: " + str(created_datetime), "|Max waiting: " + str(max_waiting) + "|IsVoting: " + str(drive.get("b_voting",False)))
            t = Thread(target=OrderLifeCycle, args=(drive,driver), daemon=True)
            t.start()
    print("Done!------------------------------------")

async def main():

    multiuser = GetUserInfo(MULTIUSER_EMAIL)
    multiuser_auth = {
        "token": None,
        "u_hash": None
    }
    if multiuser["status"] == "error":
        print("Multiuser not found, registering...")
        multiuser = RegisterClient(MULTIUSER_EMAIL, "testmultiuser")
        multiuser = GetUserInfo(MULTIUSER_EMAIL)
        multiuser_auth = {
            "token": multiuser["data"]["token"],
            "u_hash": multiuser["data"]["u_hash"]
        }
        multiuser = multiuser["data"]["user"][list(multiuser["data"]["user"].keys())[0]]
    else:
        multiuser_auth = {
            "token": multiuser["data"]["token"],
            "u_hash": multiuser["data"]["u_hash"]
        }
        multiuser = multiuser["data"]["user"][list(multiuser["data"]["user"].keys())[0]]
    print("Multiuser id: " + str(multiuser["u_id"]))
    print("Multiuser RefCode: " + multiuser["ref_code"])
    
    driver = GetUserInfo(DRIVER_EMAIL)
    if driver["status"] == "error":
        print("Driver not found, registering...")
        driver = RegisterClient(DRIVER_EMAIL, "testdriver")
        driver = GetUserInfo(DRIVER_EMAIL)
        driver_auth = {
            "token": driver["data"]["token"],
            "u_hash": driver["data"]["u_hash"]
        }
        driver = driver["data"]["user"][list(driver["data"]["user"].keys())[0]]
    else:
        driver_auth = {
            "token": driver["data"]["token"],
            "u_hash": driver["data"]["u_hash"]
        }
        driver = driver["data"]["user"][list(driver["data"]["user"].keys())[0]]
    print("Driver id: " + str(driver["u_id"]))

    cars = make_request(url_prefix+"/user/"+str(driver["u_id"])+"/car",{"token": GetAdminHashAndToken()[0],"u_hash": GetAdminHashAndToken()[1]})["data"]["car"]
    car_id = -1
    if len(cars) == 0:
        car = make_request(url_prefix+"/car",{
            "token": driver_auth["token"],
            "u_hash": driver_auth["u_hash"],

            "data": json.dumps({
                "u_id": str(driver["u_id"]),
                "seats": 2,
                "registration_plate": 1,
                "cc_id": 1,
            })
        })
        print("Car created with id: " + str(car["data"]["car"]["c_id"]))
    else:
        car_id = list(cars.keys())[0]
    print("Car id: " + str(car_id))
    driver = {
        "id": driver["u_id"],
        "car_id": car_id,
        "auth": driver_auth
    }

    while True:
        await loop(driver,multiuser)
        await asyncio.sleep(LOOP_PERIOD_SECONDS)

print("Starting...")
asyncio.run(main())

print("TEST POINT")
import datetime
import json

from api_lib import *
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

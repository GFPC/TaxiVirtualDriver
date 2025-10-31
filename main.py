print("TEST POINT")
import datetime
import json

import sys
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
THREADS_LIMIT = config["THREADS_LIMIT"]

def findCarForOrder(cars:dict, order_carClass: str | None):
    if isinstance(order_carClass, str):
        cars = [car for car in cars if car["cc_id"] == order_carClass]
    if len(cars) == 0:
        return None
    return cars[0]["c_id"]

class DriveActions:
    class State:
        def __init__(self, name, time):
            self.name = name
            self.time = time
        def __repr__(self):
            return self.name
    ARRIVE = State("arrive", WAIT_AFTER_ARRIVE_STATE)
    START = State("start", WAIT_AFTER_START_STATE)
    COMPLETE = State("complete", 0)

def set_drive_state(state: DriveActions.State,b_id, u_id):
    data = {
        "token": GetAdminHashAndToken()[0],
        "u_hash": GetAdminHashAndToken()[1],
        "u_a_id": u_id,
        "action": "",
    }
    if state == DriveActions.ARRIVE:
        data["action"] = "set_arrive_state"
    elif state == DriveActions.START:
        data["action"] = "set_start_state"
    elif state == DriveActions.COMPLETE:
        data["action"] = "set_complete_state"
    else:
        print(state)
        raise Exception("Unknown state, ")
    data = make_request(url_prefix + "drive/get/" + str(b_id), data=data)
    print("API->",state,":",b_id, 'status:', data.get("status","error"))
    if data["status"] == "error":
        print(json.dumps(data,indent=4))
    time.sleep(state.time)

def OrderLifeCycle(drive, driver):
    order_id = drive["b_id"]

    car = findCarForOrder(driver["cars"], drive["b_car_class"] )

    #1 accept
    data = {
        "token": GetAdminHashAndToken()[0],
        "u_hash": GetAdminHashAndToken()[1],
        "u_a_id": driver["id"],
        "action":"set_performer",
        "performer":1,
        "data": json.dumps({
            "c_id": car,
            "c_payment_way": 1,
            "c_options": {}
        })
    }

    if drive.get("b_voting")==1:
        driver_code = make_request(url_prefix + "drive/get/" + str(order_id), data={"token": GetAdminHashAndToken()[0], "u_hash": GetAdminHashAndToken()[1]})["data"]["booking"][str(order_id)]["b_driver_code"]
        data["b_driver_code"] = driver_code
        res = make_request(url_prefix + "drive/get/" + str(order_id), data=data)
        if res["status"] == "error" and res.get("message", "") == "wrong driver code":
            exit(1)
            pass
        elif res["status"] == "success":
            pass
        else:
            print("VOTING->Accept Error, response: ", json.dumps(res, indent=4))
            exit(1)
    else:
        data = make_request(url_prefix + "drive/get/" + str(order_id), data=data)
    print("API->Accept:",order_id, 'status:', data.get("status","error"), data)

    start_datetime = int(datetime.datetime.utcfromtimestamp(
        datetime.datetime.strptime(drive["b_start_datetime"], "%Y-%m-%d %H:%M:%S%z").timestamp()).timestamp())
    current_time = int(datetime.datetime.utcnow().timestamp())

    time.sleep(WAIT_AFTER_ACCEPT_STATE)

    if start_datetime > current_time:
        print("HYBERNATE->Order:",order_id, "for", start_datetime - current_time, "seconds")
        time.sleep(start_datetime - current_time)

    # 2 arrive
    if drive.get("b_voting") != 1:
        set_drive_state(DriveActions.ARRIVE, order_id, driver["id"])
    #3 start
    set_drive_state(DriveActions.START, order_id, driver["id"])
    #4 end
    set_drive_state(DriveActions.COMPLETE, order_id, driver["id"])

async def loop(driver, multiuser):
    drives_list = NowDrivesList()
    print("ID\tStart\tSecsRemainingForStart\tExpr")
    for i in drives_list["data"]["booking"]:
        drive = drives_list["data"]["booking"][i]

        created_datetime = drive["b_created"]
        max_waiting = drive["b_max_waiting"]
        user_id = drive["u_id"]

        user = make_request(url_prefix + "user/" + str(user_id),{"token": GetAdminHashAndToken()[0], "u_hash": GetAdminHashAndToken()[1]})
        if user["status"] == "error":
            print("User id: " + str(user_id) + " not found")
            continue
        user = user["data"]["user"][str(user_id)]


        created_datetime = int(datetime.datetime.utcfromtimestamp(datetime.datetime.strptime(created_datetime, "%Y-%m-%d %H:%M:%S%z").timestamp()).timestamp())

        current_time = int(datetime.datetime.utcnow().timestamp())

        print(str(drive["b_id"]) + "\t" + str(drive["b_start_datetime"]) + "\t" + str(current_time - created_datetime) + "\t" + str(current_time - (created_datetime + TAKE_AFTER_SECONDS)) + "\t" + str(str(user["referrer_u_id"]).lower() + "|" + str(multiuser["u_id"]).lower()))
        threads_limit = THREADS_LIMIT if THREADS_LIMIT else 10
        threads_count = 0
        if current_time - (created_datetime + TAKE_AFTER_SECONDS) > 0 and str(user["referrer_u_id"]).lower() == str(multiuser["u_id"]).lower() and str(drive["b_state"]) == "1":
            print("Founded suitable drive| id: " + str(drive["b_id"]), "|User id: " + str(user_id), "|Start datetime: " + str(created_datetime), "|Max waiting: " + str(max_waiting) + "|IsVoting: " + str(drive.get("b_voting",False)))
            if threads_count < threads_limit:
                t = Thread(target=OrderLifeCycle, args=(drive, driver), daemon=True)
                t.start()
                threads_count += 1
            else:
                print("Threads limit reached, waiting...")
                while threads_count >= threads_limit:
                    time.sleep(1)
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
        cars = list(cars.values())
        cars = [{"c_id": car["c_id"], "cc_id": car["cc_id"]} for car in cars ]
    driver = {
        "id": driver["u_id"],
        "cars": cars,
        "auth": driver_auth
    }

    while True:
        await loop(driver,multiuser)
        await asyncio.sleep(LOOP_PERIOD_SECONDS)

asyncio.run(main())

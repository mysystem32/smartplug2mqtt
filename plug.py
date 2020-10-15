#!/usr/bin/python3

# Alberto - 10 Oct 2020
# Interface between tuya smart monitoring plug and mqtt
# Version 1.0
# TODO: Allow for cmnd/plug11-sample/POWER to set plug power

import sys
import time
import logging
import signal
import json
import os.path
import threading
import queue

from tuyaface.tuyaclient import TuyaClient
import paho.mqtt.publish as mqtt_publish


# Globals
tuya_client = None
SLEEP = 30
MAX_SLEEP = 300
FNAME = None
TTY = True

mqtt_hostname = "mosquitto"
mqtt_port = 1883
mqtt_auth = {'username': "admin", 'password': "ppppppppp"}

q = queue.SimpleQueue()

PLUG = dict()

def log_it(s: str):
    if TTY:
        print(time.strftime("%F %X"), s)
    logging.info(s)


def sys_exit(sig, frame):
    # Close connections and exit
    global TTY, tuya_client, PLUG, FNAME
    TTY = True
    log_it(f"SIGNAL {sig} RECEIVED ON {FNAME}")
    save_json(PLUG,FNAME)
    if tuya_client:
        log_it("tuya_client.stop_client")
        tuya_client.stop_client()
    log_it(f"SHUTDOWN {FNAME}")
    logging.shutdown()
    sys.exit(1)


def save_json(data: dict, fname: str, verbose: bool = True):
    if verbose:
        log_it(f"save to '{fname}'")
    fp = open(fname, 'w')
    json.dump(data, fp, indent=4, sort_keys=True)
    fp.close()


def load_json(fname: str) -> dict:
    log_it(f"load from '{fname}'")
    fp = open(fname, 'r')
    data = json.load(fp)
    fp.close()
    return data


def check_day_rollover():
    # check if we 00h00
    tm_prev = PLUG['SENSOR']['Time']
    tm_now  = PLUG['SENSOR']['Time'] = time.strftime("%FT%X")
    if (tm_now[:10] != tm_prev[:10]):
        log_it(f"DAY ROLLOVER {tm_prev} -> {tm_now}")
        PLUG['SENSOR']['ENERGY']['Yesterday'] = PLUG['SENSOR']['ENERGY']['Today']
        PLUG['SENSOR']['ENERGY']['Today'] = 0.0


def secs_diff(tm_now: str, tm_prev: str):
    t_now  = time.strptime(tm_now,  "%Y-%m-%dT%H:%M:%S")
    t_prev = time.strptime(tm_prev, "%Y-%m-%dT%H:%M:%S")
    return (time.mktime(t_now) - time.mktime(t_prev))  # seconds


def calc_consumption():
    # calculate consumption since previous reading
    seconds = secs_diff(PLUG['SENSOR']['Time'], PLUG['PREV']['Time'])
    if (seconds > 0):
        Prev_W = PLUG['PREV']['Power']
        Power_W = PLUG['SENSOR']['ENERGY']['Power']
        rate = float(seconds) / 3600.0
        kWh = Power_W / 1000.0 * rate
        PLUG['SENSOR']['ENERGY']['Today'] += kWh
        PLUG['SENSOR']['ENERGY']['Total'] += kWh
        if (Power_W > 0 or Prev_W > 0):
            log_it("Consumption seconds={}, Power_W={}, Wh={:0.3f}, Today={:0.3f}, Total={:0.3f}".format(
                seconds, Power_W, kWh*1000,
                PLUG['SENSOR']['ENERGY']['Today'], PLUG['SENSOR']['ENERGY']['Total']))


def update_reading(data: dict):
    # upadate PLUG with latest data points
    dps = data['dps']  # Data Points
    if '1' in dps:
        PLUG['STATE']['Time'] = time.strftime("%FT%X")
        PLUG['STATE']['POWER'] = "ON" if dps['1'] else "OFF"
    if '19' in dps:
        PLUG['SENSOR']['ENERGY']['Power'] = float(dps['19'])/10.0  # Power - W
    if '18' in dps:
        PLUG['SENSOR']['ENERGY']['Current'] = float(dps['18'])/1000.0  # Current - mA
    if '20' in dps:
        PLUG['SENSOR']['ENERGY']['Voltage'] = float(dps['20'])/10.0  # Voltage - V

def update_prev():
    # What changed?
    state_change  = (PLUG['PREV']['POWER']   != PLUG['STATE']['POWER'])
    sensor_change = (PLUG['PREV']['Power']   != PLUG['SENSOR']['ENERGY']['Power'] or
                     PLUG['PREV']['Current'] != PLUG['SENSOR']['ENERGY']['Current'] or
                     PLUG['PREV']['Voltage'] != PLUG['SENSOR']['ENERGY']['Voltage'])

    # update PREV so we can detect changes in dps
    PLUG['PREV']['POWER']   = PLUG['STATE']['POWER']
    PLUG['PREV']['Power']   = PLUG['SENSOR']['ENERGY']['Power']
    PLUG['PREV']['Current'] = PLUG['SENSOR']['ENERGY']['Current']
    PLUG['PREV']['Voltage'] = PLUG['SENSOR']['ENERGY']['Voltage']
    PLUG['PREV']['Time']    = PLUG['SENSOR']['Time']

    return state_change, sensor_change


def process_message(m: str, data: dict):
    #print(data)
    #devId = data['devId']
    check_day_rollover()
    update_reading(data)

    calc_consumption()
    state_change, sensor_change = update_prev()

    PLUG['HEARTBEAT'] += SLEEP  # seconds

    if (sensor_change or state_change or PLUG['HEARTBEAT'] >= MAX_SLEEP):
        save_json(PLUG, FNAME, False)
        mpublish(m, 'STATE', state_change)
        mpublish(m, 'SENSOR', True)
        PLUG['HEARTBEAT'] = 0

    if TTY:
        print("%3d" % (PLUG['HEARTBEAT']), end="\r")


def mpublish(m: str, t: str, verbose: bool = True):
    # make a local copy of PLUG
    P = dict(PLUG)

    # round some of the output values
    P['SENSOR']['ENERGY']['Today'] =     round(P['SENSOR']['ENERGY']['Today'], 3)
    P['SENSOR']['ENERGY']['Total'] =     round(P['SENSOR']['ENERGY']['Total'], 3)
    P['SENSOR']['ENERGY']['Yesterday'] = round(P['SENSOR']['ENERGY']['Yesterday'], 3)

    # publish
    topic = "tele/" + P['NAME'] + "/" + t
    payload = json.dumps(P[t])
    if verbose:
        log_it("{:03d} {} {}, payload={}, published".format(
            P['HEARTBEAT'], m, topic, payload))
    try:
        mqtt_publish.single(topic=topic, payload=payload, qos=0, retain=False,
                            hostname=mqtt_hostname, port=mqtt_port, auth=mqtt_auth)
    except Exception as err:
        log_it(f"ERROR: MOSQUITTO: Connection error={err}, sleep 60...")
        time.sleep(10) # wait a while before publishing next message
        # sys_exit(err,None)


def processQ():
    while True:
        # Block until q.put
        msg = q.get()
        if msg[1]:
           process_message(msg[0], msg[1])


def on_status(data: dict, status):
    # will get called whenever there is a status change
    q.put(["on_s", dict(data)]) # Q a copy of data


def on_connection(value: bool):
    # will get called whenever we connect/disconnnect
    log_it(f"on_connection={value}")
    #time.sleep(2)
    #if value: 
    #    q.put(["on_c", tuya_client.status()])


#################
# START OF MAIN #
#################

if (len(sys.argv) != 2):
    print("usage: plug.py plugname.json")
    sys.exit(1)

FNAME = str(sys.argv[1])
logname = os.path.splitext(FNAME)[0] + ".log"
logging.basicConfig(format='%(asctime)s %(message)s', filename=logname, level=logging.INFO)

log_it("STARTING plug.py {} with log={}".format(FNAME, logname))

PLUG = load_json(FNAME)
PLUG['HEARTBEAT'] = 0
PLUG['PREV']['Voltage'] = -0.01
save_json(PLUG, FNAME)

signal.signal(signal.SIGINT,  sys_exit)
signal.signal(signal.SIGTERM, sys_exit)

# Start worker thread for Queue
threading.Thread(target=processQ, daemon=True).start()

# Connect to Tuya
# we need a copy of device, as tuyaface modifies it and we can't serialise the changes
device = dict(PLUG['device'])
tuya_client = TuyaClient(device, on_status, on_connection)
tuya_client.start()
time.sleep(5)

TTY = sys.stdout.isatty()

while True:
    data = tuya_client.status()
    q.put(["poll", data])
    time.sleep(SLEEP)

tuya_client.stop_client()

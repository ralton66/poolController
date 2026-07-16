# SPDX-FileCopyrightText: Copyright (C) ARDUINO SRL (http://www.arduino.cc)
#
# SPDX-License-Identifier: MPL-2.0

import os
import sys
from pathlib import Path
from arduino.app_utils import App, Bridge

sys.path.insert(0, str(Path(__file__).resolve().parent))

from arduino.app_utils import *
from arduino.app_bricks.web_ui import WebUI
from arduino.app_utils import App, Bridge

from bridge.client import get_client
from cloud.arduino_sync import CloudSync
from model.pool_state import PoolState
from services.controller import PoolController
from services.monitor import PoolMonitor

TEST_LED = True
TEST_CLOUD = True
DEBUG_PROTOCOL = False
led_is_on = False
pool_is_on = False
spa_is_on = False

PKT_PDA_SELECT = bytes([
    0x10, 0x02, 0x00, 0x01, 0x50, 0x04, 0x67, 0x10, 0x03
])

bridge = get_client()
pool_state = PoolState(bridge)
ui = WebUI()

def broadcast_state():
    snap = monitor.get_snapshot()
    print("broadcast_state: ", snap)
    ui.send_message("state_update", snap)
    if DEBUG_PROTOCOL:
        ui.send_message("protocol_update", snap.get("last_packet", snap))
    cloud_sync.on_state_changed(pool_state)

def on_state_updated(_state: PoolState):
    broadcast_state()

controller = PoolController(bridge, pool_state, on_tx=lambda h: ui.send_message("protocol_tx", {"hex": h}))
monitor = PoolMonitor(pool_state, bridge, controller, on_update=on_state_updated)
cloud_sync = CloudSync(pool_state, bridge, controller, on_state_push=lambda _: broadcast_state())

def on_pda_packet(hex_payload: str):
    monitor.handle_hex_payload(hex_payload)

def on_get_state(client, data):
    print("State Update")
    ui.send_message("state_update", monitor.get_snapshot(), client)

def on_get_initial_state(client, data):
    on_get_state(client, data)
    if TEST_LED:
        print("led_status_update")

def on_set_filter(client, data): 
    print("main: on_set_filter")
    controller.pool_filter()

def on_set_pool_heater(client, data):
    controller.pool_heater()

def on_set_pool_temp(client, data): 
    print("main: on_set_pool_temp ")
    try:
        temp_f = int(data.get("temp_f", 89)) if isinstance(data, dict) else 89
    except (TypeError, ValueError):
        temp_f = 89
    controller.pool_temp(temp_f)

def on_set_pool_lights(client, data):
    controller.set_pool_lights()

def on_set_filter_rpm(client, data): 
    rpm = None
    if isinstance(data, dict):
        if "rpm" in data:
            try:
                rpm = int(data["rpm"])
            except (TypeError, ValueError):
                pass
    controller.pool_filter_rpm(rpm=rpm)

def on_set_spa(client, data):
    controller.spa_on()

def on_set_spa_heater(client, data):
    controller.spa_heater()

def on_set_spa_temp(client, data):
    print("main: on_set_spa_temp ")
    try:
        temp_f = int(data.get("temp_f", 102)) if isinstance(data, dict) else 102
    except (TypeError, ValueError):
        temp_f = 102
    controller.spa_temp(temp_f)

def on_set_spa_lights(client, data):
    controller.set_spa_lights()

def on_set_jets(client, data):
    controller.jets()

def on_all_off(client, data):
    controller.all_off()

def on_reset(client, data):
    controller.reset()

def on_pda(client, data):
    controller.pda()

def on_get_protocol_state(client, data):
    ui.send_message("protocol_update", pool_state.last_packet, client)


def get_led_status():
    return {
        "led_is_on": led_is_on,
        "status_text": "LED IS ON" if led_is_on else "LED IS OFF",
    }

def get_spa_status():
    return {
        "spa_is_on": spa_is_on,
        "status_text": "SPA IS ON" if spa_is_on else "SPA IS OFF",
    }

def get_pool_status():
    return {
        "pool_is_on": pool_is_on,
        "status_text": "POOL IS ON" if pool_is_on else "POOL IS OFF",
    }

def toggle_led_state(client, data):
    global led_is_on
    led_is_on = not led_is_on
    Bridge.call("set_led_state", led_is_on)
    ui.send_message("led_status_update", get_led_status())

def toggle_spa_state(client, data):
    global spa_is_on
    spa_is_on = not spa_is_on
    Bridge.call("set_spa_state", spa_is_on)
    ui.send_message("spa_status_update", get_spa_status())

def toggle_pool_state(client, data):
    global pool_is_on
    pool_is_on = not pool_is_on
    Bridge.call("set_pool_state", pool_is_on)
    ui.send_message("pool_status_update", get_pool_status())

# Callback to get pda packet info coming from panel
Bridge.provide("pda_packet", on_pda_packet)

ui.on_message("get_state", on_get_state)
ui.on_message("get_initial_state", on_get_initial_state)
ui.on_message("set_spa", on_set_spa)
ui.on_message("set_filter", on_set_filter)
ui.on_message("set_filter_rpm", on_set_filter_rpm)
ui.on_message("set_pool_heater", on_set_pool_heater)
ui.on_message("set_pool_lights", on_set_pool_lights)
ui.on_message("set_pool_temp", on_set_pool_temp)
ui.on_message("set_spa_temp", on_set_spa_temp)
ui.on_message("set_spa_heater", on_set_spa_heater)
ui.on_message("set_spa_lights", on_set_spa_lights)
ui.on_message("set_jets", on_set_jets)
ui.on_message("all_off", on_all_off)
ui.on_message("pda", on_pda)
ui.on_message("reset", on_reset)

if TEST_LED:
    ui.on_message("toggle_led", toggle_led_state)

controller.start()

if TEST_CLOUD:
    cloud_sync.start()

App.run()

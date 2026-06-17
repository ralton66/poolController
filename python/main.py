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
from services.monitor import PoolMonitor, StateMachine, ControlState
from services.test_mode import TestModeService, is_test_mode

TEST_LED = True
TEST_CLOUD = True
DEBUG_PROTOCOL = False

PKT_PDA_SELECT = bytes([
    0x10, 0x02, 0x00, 0x01, 0x50, 0x04, 0x67, 0x10, 0x03
])

bridge = get_client()
pool_state = PoolState()
sm = StateMachine(state=ControlState.IDLE)
ui = WebUI()


def broadcast_state():
    snap = monitor.get_snapshot()
    ui.send_message("state_update", snap)
    if DEBUG_PROTOCOL:
        ui.send_message("protocol_update", snap.get("last_packet", snap))
    cloud_sync.on_state_changed(pool_state)


def on_state_updated(_state: PoolState):
    broadcast_state()


controller = PoolController(bridge, pool_state, on_tx=lambda h: ui.send_message("protocol_tx", {"hex": h}))

monitor = PoolMonitor(pool_state, bridge, controller, sm, on_update=on_state_updated)
cloud_sync = CloudSync(pool_state, bridge, controller, on_state_push=lambda _: broadcast_state())


def on_pda_packet(hex_payload: str):
    if is_test_mode():
        return
    monitor.handle_hex_payload(hex_payload)


def on_get_state(client, data):
    ui.send_message("state_update", monitor.get_snapshot(), client)
   

def on_get_initial_state(client, data):
    on_get_state(client, data)
    if TEST_LED:
        print("led_status_update")


def on_set_spa(client, data):
    try:
        temp_f = int(data.get("temp_f", 102)) if isinstance(data, dict) else 102
    except (TypeError, ValueError):
        temp_f = 102
    controller.spa_on(temp_f)


def on_set_filter(client, data):
    rpm = None
    preset = None
    if isinstance(data, dict):
        if "rpm" in data:
            try:
                rpm = int(data["rpm"])
            except (TypeError, ValueError):
                pass
        preset = data.get("preset")
    controller.pool_filter(rpm=rpm, preset=preset)


def on_set_lights(client, data):
    on = True
    target = "pool"
    if isinstance(data, dict):
        on = data.get("on", True)
        if isinstance(on, str):
            on = on.lower() in ("1", "true", "on")
        target = data.get("target", "pool")
    controller.set_lights(bool(on), target)


def on_all_off(client, data):
    controller.all_off()


def on_reset(client, data):
    controller.reset()


def on_send_test_tx(client, data):
    print("")

def on_inject_test_rx(client, data):
    if is_test_mode():
        print("")
    else:
        bridge.inject_test_packet()


def on_get_protocol_state(client, data):
    ui.send_message("protocol_update", pool_state.last_packet, client)


led_is_on = False

def get_led_status():
    return {
        "led_is_on": led_is_on,
        "status_text": "LED IS ON" if led_is_on else "LED IS OFF",
    }


def toggle_led_state(client, data):
    global led_is_on
    led_is_on = not led_is_on
    Bridge.call("set_led_state", led_is_on)
    ui.send_message("led_status_update", get_led_status())


Bridge.provide("pda_packet", on_pda_packet)

ui.on_message("get_state", on_get_state)
ui.on_message("get_initial_state", on_get_initial_state)
ui.on_message("set_spa", on_set_spa)
ui.on_message("set_filter", on_set_filter)
ui.on_message("set_lights", on_set_lights)
ui.on_message("all_off", on_all_off)
ui.on_message("reset", on_reset)

if TEST_LED:
    ui.on_message("toggle_led", toggle_led_state)

controller.start()

if TEST_CLOUD:
    cloud_sync.start()

App.run()

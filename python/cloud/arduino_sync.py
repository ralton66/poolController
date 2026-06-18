# SPDX-FileCopyrightText: Copyright (C) ARDUINO SRL (http://www.arduino.cc)
# SPDX-License-Identifier: MPL-2.0

"""Arduino Cloud subset sync (AC-12)."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Callable

from model.pool_state import PoolMode, PoolState
from model.commands import CommandType
from model.commands import Command
from bridge.client import BridgeClient

if TYPE_CHECKING:
    from services.controller import PoolController

try:
    from arduino.app_bricks.arduino_cloud import ArduinoCloud
except ImportError:
    ArduinoCloud = None  # type: ignore

class CloudSync:
    """Map PoolState ↔ Cloud Thing properties; writes enqueue controller commands."""

    def __init__(
        self,
        state: PoolState,
        bridge: BridgeClient,
        controller: PoolController,
        on_state_push: Callable[[dict], None] | None = None,
    ):
        self.state = state
        self.bridge = bridge
        self.controller = controller
        self._on_state_push = on_state_push
        self._cloud = None
        self._vars: dict = {}

    def start(self) -> None:
        try:
            self._cloud = ArduinoCloud()
        except (TypeError, ValueError):
            return
        self._register_properties()
        #self.push_state()

    def led_callback(self, client: object, value: bool):
        """Callback function to handle LED blink updates from cloud."""
        print(f"LED blink value updated from cloud: {value}")
        # Call a function in the sketch, using the Bridge helper library, to control the state of the LED connected to the microcontroller.
        # This performs a RPC call and allows the Python code and the Sketch code to communicate.
        self.bridge.toggle_led(value)

    def _register_properties(self) -> None:
        c = self._cloud

        def mode_write(_client, value: str):
            v = (value or "off").lower()
            if v == "spa":
                t = self.state.spa_setpoint_f or 102
                self.controller.enqueue(
                    Command(type=CommandType.SPA_ON, temp_f=t)
                )
            elif v == "pool":
                self.controller.pool_filter()
            else:
                self.controller.all_off()

        def spa_target_write(_client, value):
            try:
                temp_f = int(value)
            except (TypeError, ValueError):
                return
            self.controller.enqueue(
                Command(type=CommandType.SPA_ON, temp_f=temp_f)
            )

        def lights_write(_client, value):
            on = value in (True, 1, "1", "true", "on")
            self.controller.set_lights(on, "pool")
        
        c.register("led", value=False, on_write=self.led_callback)
        c.register("air_temp_f", value=0)
        c.register("water_temp_f", value=0)
        #c.register("mode", value="off", on_write=mode_write)
        #c.register("filter_pump_on", value=False)
        #c.register("filter_rpm", value=0)
        #c.register("spa_target_f", value=102, on_write=spa_target_write)
        #c.register("lights_on", value=False, on_write=lights_write)
        self._read_keys = (
            "water_temp_f",
            "air_temp_f",
        )
        
        c.air_temp_f = 25
        #c.water_temp_f = 85

    def _push_read(self, name: str, value) -> None:
        if value is None or not self._cloud:
            return
        c = self._cloud
        print(f"Cloud sync: {name} -> {value}")

        try:
            setattr(c, name, value)
        except AttributeError:
            print(f"ERROR: The variable '{name}' does not exist on your Arduino Cloud dashboard.")
        except Exception as e:
            print(f"Unexpected error syncing {name}: {e}")

    def on_state_changed(self, state: PoolState) -> None:
        if not self._cloud:
            return
        snap = state.cloud_read_dict()
        for key in self._read_keys:
            val = snap.get(key)
            #print(f"Cloud sync: {key} -> {val}")
            if val is not None:
                self._push_read(key, val)
        #if self._on_state_push:
        #    self._on_state_push(state.to_dict())

    def push_state(self) -> None:
        self.on_state_changed(self.state)

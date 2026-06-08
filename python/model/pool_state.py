# SPDX-FileCopyrightText: Copyright (C) ARDUINO SRL (http://www.arduino.cc)
# SPDX-License-Identifier: MPL-2.0

"""Pool equipment and mode state (single source of truth for UI and Cloud)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from protocol.pda_messages import ParsedPacket

STALE_SECONDS = 30


class PoolMode(str, Enum):
    OFF = "off"
    POOL = "pool"
    SPA = "spa"


@dataclass
class PoolState:
    mode: PoolMode = PoolMode.OFF
    air_temp_f: int | None = None
    pool_temp_f: int | None = None
    spa_temp_f: int | None = None
    pool_setpoint_f: int | None = None
    spa_setpoint_f: int | None = None
    filter_pump_on: bool | None = None
    filter_rpm: int | None = None
    aux_pump_on: bool | None = None
    heater_on: bool | None = None
    pool_light_on: bool | None = None
    spa_light_on: bool | None = None
    valve: str | None = None
    swg_status: str | None = None
    connection_ok: bool = False
    undefined_state: bool = False
    last_update: float = 0.0
    last_error: str | None = None
    last_packet: dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        self.last_update = time.time()
        self.connection_ok = True

    def check_staleness(self) -> None:
        if self.last_update <= 0:
            self.connection_ok = False
            return
        if time.time() - self.last_update > STALE_SECONDS:
            self.connection_ok = False

    def apply_parsed(self, parsed: ParsedPacket, hex_payload: str = "") -> None:
        """Merge one parsed PDA packet into observable state."""
        self.touch()

        if parsed.frame.cmd == 0x08:
            line_num = parsed.frame.data[0] 
            parsed.fields["line"] = line_num
            print(f"Highlighted Line: {line_num}")
        
        if parsed.frame.dest == 0x60 and parsed.frame.cmd == 0x04:
            print(f"Text: {parsed.text}")

        pkt = parsed.to_dict()
        pkt["hex"] = hex_payload
        self.last_packet = pkt

        fields = parsed.fields
        print(f"Applying parsed packet fields: {fields}")
        temp_type = fields.get("temp_type")
        temp_f = fields.get("temp_f")
        if temp_type == "air" and temp_f is not None:
            self.air_temp_f = temp_f
        elif temp_type == "pool" and temp_f is not None:
            self.pool_temp_f = temp_f
        elif temp_type == "spa" and temp_f is not None:
            self.spa_temp_f = temp_f

        setpoint_type = fields.get("setpoint_type")
        setpoint_f = fields.get("setpoint_f")
        if setpoint_type == "pool" and setpoint_f is not None:
            self.pool_setpoint_f = setpoint_f
        elif setpoint_type == "spa" and setpoint_f is not None:
            self.spa_setpoint_f = setpoint_f

        if "rpm" in fields:
            self.filter_rpm = fields["rpm"]
            self.filter_pump_on = fields["rpm"] > 0

        text = (parsed.text or "").upper()
        if "FILTER" in text and "OFF" in text:
            self.filter_pump_on = False
            self.filter_rpm = 0
        elif "FILTER" in text and ("ON" in text or "RPM" in text):
            print(f"Setting filter pump on based on text='{text}'")
            self.filter_pump_on = True

        if "HEATER" in text:
            self.heater_on = "ON" in text and "OFF" not in text

        if "POOL LIGHT" in text or text.startswith("LIGHT POOL"):
            self.pool_light_on = "ON" in text
        if "SPA LIGHT" in text:
            self.spa_light_on = "ON" in text

        if "JET" in text or "AUX" in text:
            self.aux_pump_on = "ON" in text

        if "SALT" in text or "CHLOR" in text or "SWG" in text:
            self.swg_status = parsed.text

        if "VALVE" in text:
            if "SPA" in text:
                self.valve = "spa"
            elif "POOL" in text:
                self.valve = "pool"
            else:
                self.valve = parsed.value or text

        if text == "SPA MODE" or text.startswith("SPA MODE"):
            self.mode = PoolMode.SPA
        elif text == "POOL MODE" or text.startswith("POOL MODE"):
            self.mode = PoolMode.POOL
        elif "ALL OFF" in text:
            self.mode = PoolMode.OFF
            self.filter_pump_on = False

        self._check_consistency()

    def _check_consistency(self) -> None:
        """Flag undefined state when mode and equipment disagree."""
        if self.mode == PoolMode.SPA and self.valve == "pool":
            self.undefined_state = True
        elif self.mode == PoolMode.OFF and self.filter_pump_on is True:
            self.undefined_state = True
        else:
            self.undefined_state = False

    def to_dict(self) -> dict[str, Any]:
        self.check_staleness()
        return {
            "mode": self.mode.value,
            "air_temp_f": self.air_temp_f,
            "pool_temp_f": self.pool_temp_f,
            "spa_temp_f": self.spa_temp_f,
            "pool_setpoint_f": self.pool_setpoint_f,
            "spa_setpoint_f": self.spa_setpoint_f,
            "filter_pump_on": self.filter_pump_on,
            "filter_rpm": self.filter_rpm,
            "aux_pump_on": self.aux_pump_on,
            "heater_on": self.heater_on,
            "pool_light_on": self.pool_light_on,
            "spa_light_on": self.spa_light_on,
            "valve": self.valve,
            "swg_status": self.swg_status,
            "connection_ok": self.connection_ok,
            "undefined_state": self.undefined_state,
            "last_update": self.last_update,
            "last_error": self.last_error,
            "last_packet": dict(self.last_packet),
        }

    def cloud_read_dict(self) -> dict[str, Any]:
        """Subset exposed as Cloud read properties (AC-12)."""
        d = self.to_dict()
        return {
            "pool_temp_f": d["pool_temp_f"],
            "spa_temp_f": d["spa_temp_f"],
            "mode": d["mode"],
            "filter_pump_on": d["filter_pump_on"],
            "filter_rpm": d["filter_rpm"],
        }

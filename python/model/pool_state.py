# SPDX-FileCopyrightText: Copyright (C) ARDUINO SRL (http://www.arduino.cc)
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from protocol.pda_messages import ParsedPacket
from bridge.client import BridgeClient, Command, CommandType

STALE_SECONDS = 60

class PoolMode(str, Enum):
    OFF = "Off"
    POOL = "Pool"
    SPA = "Spa"

class PoolState:
    

    def __init__(self, bridge: BridgeClient):

        self.bridge = bridge
        # Master hardware display memory tracking. Keys are raw Jandy lead bytes.
        self.virtual_screen: dict[int, str] = {}
        self.line_number = 0
        self.line_text = b""
        self.off_ctr: int = 0
        
        # Observable parsed properties
        self.mode = PoolMode.OFF
        self.air_temp_f: int | None = None
        self.water_temp_f: int | None = None
        self.water_setpoint_f: int | None = None
        self.target_temp_f: int | None = None
        self.salt_ppm: int | None = None
        self.swg_percent: int | None = None
        self.filter_rpm: int | None = None
        self.filter_watts: int | None = None
        self.spa: bool = False
        self.pool: bool = False
        self.filter_pump_on: bool = False
        self.jet_pump_on: bool = False
        self.heater_on: bool = False
        self.pool_heater_on: bool = False
        self.spa_heater_on: bool = False
        self.pool_light_on: bool = False
        self.spa_light_on: bool = False
        self.valve: str | None = None
        self.swg_status: str | None = None
        self.time_string: str | None = None
        self.day_of_week: str | None = None
        self.undefined_state: bool = False
        self.last_error: str | None = None
        self.updated: bool = False
        
        # Watchdog Tracking
        self.last_update: float = 0.0
        self.connection_ok: bool = False
        self.screen_clr: bool = False
        self.last_packet: dict[str, Any] = {}

    def touch(self) -> None:
        self.last_update = time.time()
        self.connection_ok = True

    def check_staleness(self) -> None:
        if self.last_update <= 0:
            self.connection_ok = False
            return
        stale_threshold = STALE_SECONDS if 'STALE_SECONDS' in globals() else 10
        if time.time() - self.last_update > stale_threshold:
            self.connection_ok = False

    def apply_parsed(self, parsed: ParsedPacket, hex_payload: str = "") -> None:
        dest = parsed.frame.dest
        cmd = parsed.frame.cmd
        raw_data = parsed.frame.data

        # --- ACTION 1: SCREEN WIPE ---
        if dest == 0x60 and cmd == 0x09:
            self.touch()
            self.virtual_screen.clear()
            self.screen_clr = True

            # If updated then clear the state and get a full update.
            if(self.updated):
                print("  Main screen update complete. PoolState updated.")
                self.updated = False  # Reset the updated flag after snapshotting
                self.pool_light_on = False
                self.spa_light_on = False
                self.filter_pump_on = False
                self.jet_pump_on = False
                self.pool = False
                self.spa = False
                self.mode = PoolMode.OFF
                self.heater_on = False
                self.swg_percent = None
                self.salt_ppm = None
                self.air_temp_f = None
                self.water_temp_f = None
                self.undefined_state = False
                self.filter_rpm = None
                self.filter_watts = None 
            return

        # --- ACTION 2: DATA STREAM GATHERING ---
        if dest == 0x60 and cmd == 0x04:
            if not raw_data:
                return
            
            self.touch()
            pkt = parsed.to_dict()
            pkt["hex"] = hex_payload
            self.last_packet = pkt  

            lead_byte = raw_data[0]
            self.line_number = lead_byte
            raw_text_bytes = raw_data[1:]
            
            
            # Drop trailing stale buffer data past null terminators
            if b"\x00" in raw_text_bytes:
                raw_text_bytes = raw_text_bytes.split(b"\x00")[0]

            # Convert to string and clean up Jandy's unique symbols
            text_chunk = raw_text_bytes.decode("ascii", errors="replace").strip()
            text_chunk = text_chunk.replace("`", "F").upper()

            # Store in line_text for _parse_line
            self.line_text = text_chunk
            flags = 0

            print(f"  Line # 0x{self.line_number:02X} ({self.updated}): '{self.line_text}'")
            self._parse_line()

            # Need a step to aggregate the main screen data such as pool and spa off at this point.

            if self.line_number == 130:
                #reset counter because we recieved at least a temp update
                self.off_ctr = 0
                self.bridge.got_main(True)
                self.updated = True
                self.heater_on = self.pool_heater_on  or self.spa_heater_on
            
            # Check if we are getting time updates only.
            # this indicates that the pool is off because there are no associated 
            # temperature updates on the main menu.  
            # If we get 3 time updates in a row, then we can assume the pool is off.
            if self.line_number == 64:
                self.off_ctr += 1
                print(f"  Time line counter: {self.off_ctr} ")
                if( self.off_ctr > 2):
                    self.bridge.got_main(True)
                    self.mode = PoolMode.OFF
                    self.spa = False
                    self.pool = False
                    self.filter_pump_on = False
                    self.updated = True           
        return


    def _parse_line(self):

        if "AQUAPURE" in self.line_text:
            ap_match = re.search(r"AQUAPURE\s*(\d+)\s*%", self.line_text)
            if ap_match: 
                self.swg_percent = int(ap_match.group(1))

        if "SALT" in self.line_text:
            salt_match = re.search(r"SALT\s*(\d+)", self.line_text)
            if salt_match: 
                self.salt_ppm = int(salt_match.group(1))

        # Note: slice or search flexible numeric groupings to catch trailing anomalies
        if "RPM:" in self.line_text:
            rpm_match = re.search(r"RPM:\s*(\d+)", self.line_text)
            if rpm_match: 
                self.filter_rpm = int(rpm_match.group(1))

        # 4. Parse Electrical Load draw (e.g., "WATTS: 326")
        if "WATTS:" in self.line_text:
            watts_match = re.search(r"WATTS:\s*(\d+)", self.line_text)
            if watts_match: 
                self.filter_watts = int(watts_match.group(1))

        if "POOL LIGHT" in self.line_text:
            self.pool_light_on = True

        if "SPA LIGHT" in self.line_text:
            self.spa_light_on = True

        # Check if main menu shows Pool mode ON
        if all(w in self.line_text for w in ["POOL MODE", "ON"]):
            self.filter_pump_on = True
            self.mode = PoolMode.POOL
            self.pool = True
            self.spa = False
            #print("Parseline: Pool mode is on, filter pump enabled.")

        # Check if main menu shows Spa mode on 
        if all(w in self.line_text for w in ["SPA MODE", "ON"]):
            self.filter_pump_on = True
            self.mode = PoolMode.SPA
            self.pool = False
            self.spa = True

        # Check if main menu shows Jet pump on 
        if all(w in self.line_text for w in ["JET PUMP", "ON"]):
            self.jet_pump_on = True
        
        # Check if main menu shows spa heater on 
        #############TODO: SPA HEATER TURN OFF POOL HEATER WHEN it comes through
        if all(w in self.line_text for w in ["SPA HEATER", "ON"]):
            self.spa_heater_on = True
        elif all(w in self.line_text for w in ["SPA HEATER", "OFF"]):
            self.spa_heater_on = False
        elif all(w in self.line_text for w in ["SPA HEATER", "ENA"]):
            self.spa_heater_on = True   

        # Check if main menu shows pool heater on 
        if all(w in self.line_text for w in ["POOL HEATER", "ON"]):
            self.pool_heater_on = True
        elif all(w in self.line_text for w in ["POOL HEATER", "OFF"]):
            self.pool_heater_on = False
        elif all(w in self.line_text for w in ["POOL HEATER", "ENA"]):
            self.pool_heater_on = True   


        # Parse temperature line on home screen (line 0x82) for Air and Water temps
        if self.line_number == 0x82:
            # 1. Slice the left half of the display buffer for Air Temp
            left_half = self.line_text[:8]
            air_match = re.search(r"(\d+)\s*F", left_half)
            if air_match:
                self.air_temp_f = int(air_match.group(1))

            # 2. Slice the right half of the display buffer for Water Temp
            right_half = self.line_text[8:]
            water_match = re.search(r"(\d+)\s*F", right_half)
            
            if water_match:
                self.water_temp_f = int(water_match.group(1))

        if "POOL HEAT" in self.line_text and self.line_number == 0x00:
            print("Pool Heat Menu")

        # Grab the current temp setpoint in the heater menu
        if "SET TO" in self.line_text and self.line_number == 0x03:
            print("Pool/SPA Heat Menu")

            # re.search looks for one or more digits followed by 'F'
            # 'SET TO 91FF' matches '91' in group 1
            match = re.search(r"(\d+)\s*F", self.line_text)
            
            if match:
                temp_value = int(match.group(1))
                self.target_temp_f = temp_value
                print(f"Captured valid target setpoint update: {temp_value}°F")
                self.bridge.htr_setpoint(temp_value)


        if self.line_number == 0x40:
            # Preprocessor output for this chunk will look like: "FRI  2:14PM"
            # Regex breakdown:
            # ([A-Z]{3})    -> Capture 3 uppercase letters for the Day (e.g., FRI)
            # \s+           -> Bridge any middle alignment spaces
            # (\d{1,2}:\d{2})\s*(AM|PM) -> Capture the time block and AM/PM token
            match = re.search(r"([A-Z]{3})\s+(\d{1,2}:\d{2})\s*(AM|PM)", self.line_text)
            
            if match:
                day_of_week = match.group(1)   # "FRI"
                clock_time  = match.group(2)   # "2:14"
                ampm_marker = match.group(3)   # "PM"
                
                # Combine into a clean timestamp string
                full_time_string = f"{day_of_week} {clock_time} {ampm_marker}"
                
                # Store it directly in your monitor state object
                self.time_string = full_time_string
                self.day_of_week = day_of_week


        if "ALL OFF" in self.line_text:
            self.mode = PoolMode.OFF
            self.spa = False
            self.pool = False
            self.filter_pump_on = False


    def to_dict(self) -> dict[str, Any]:
        self.check_staleness()
      
        return {
            "mode": self.mode.value if hasattr(self.mode, 'value') else self.mode,
            "air_temp_f": self.air_temp_f,
            "water_temp_f": self.water_temp_f,
            "water_setpoint_f": self.water_setpoint_f,
            "target_temp_f": self.target_temp_f,
            "salt_ppm": self.salt_ppm,
            "swg_percent": self.swg_percent,
            "filter_rpm": self.filter_rpm,
            "filter_watts": self.filter_watts,
            "filter_pump_on": self.filter_pump_on,
            "jet_pump_on": self.jet_pump_on,
            "heater_on": self.heater_on,
            "pool_light_on": self.pool_light_on,
            "spa_light_on": self.spa_light_on,
            "spa": self.spa,
            "pool": self.pool,
            "valve": self.valve,
            "swg_status": self.swg_status,
            "time": self.time_string,
            "dow": self.day_of_week,
            "off_ctr": self.off_ctr,
            "undefined_state": self.undefined_state,
            "last_error": self.last_error,
            "connection_ok": self.connection_ok
        }

    def cloud_read_dict(self) -> dict[str, Any]:
        """Subset exposed as Cloud read properties (AC-12)."""
        d = self.to_dict()
        print(f"cloud_read_dict: {d}")
        return {
            "water_temp_f": d.get("water_temp_f"),
            "air_temp_f": d.get("air_temp_f"),
            "spa": d.get("spa", False),
            "pool": d.get("pool", False),
            "temp_setpoint_f": d.get("pool_setpoint_f"),
        }

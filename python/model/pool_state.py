# SPDX-FileCopyrightText: Copyright (C) ARDUINO SRL (http://www.arduino.cc)
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
import re
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

class PoolState:
    def __init__(self):
        # Master hardware display memory tracking. Keys are raw Jandy lead bytes.
        self.virtual_screen: dict[int, str] = {}
        
        # Observable parsed properties
        self.mode = PoolMode.OFF
        self.air_temp_f: int | None = None
        self.pool_temp_f: int | None = None
        self.spa_temp_f: int | None = None
        self.pool_setpoint_f: int | None = None
        self.spa_setpoint_f: int | None = None
        
        self.salt_ppm: int | None = None
        self.aquapure_percent: int | None = None
        self.filter_rpm: int | None = None
        self.filter_watts: int | None = None
        
        self.filter_pump_on: bool = False
        self.aux_pump_on: bool = False
        self.heater_on: bool = False
        self.pool_light_on: bool = False
        self.spa_light_on: bool = False
        self.valve: str | None = None
        self.swg_status: str | None = None
        self.undefined_state: bool = False
        self.last_error: str | None = None
        
        # Watchdog Tracking
        self.last_update: float = 0.0
        self.connection_ok: bool = False
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

        # If Jandy broadcasts a Clear Screen command (0x09), wipe out old text artifacts!
        if dest == 0x60 and cmd == 0x09:
            self.touch()
            self.virtual_screen.clear()
            return

        # Handle Standard Text Messages (0x04)
        if dest == 0x60 and cmd == 0x04:
            if not raw_data:
                return
            
            self.touch()
            pkt = parsed.to_dict()
            pkt["hex"] = hex_payload
            self.last_packet = pkt  

            # Extract lead memory line coordinate
            lead_byte = raw_data[0]
            raw_text_bytes = raw_data[1:]
            
            # 🚀 Split at the first null terminator to drop stale buffer memory data
            if b"\x00" in raw_text_bytes:
                raw_text_bytes = raw_text_bytes.split(b"\x00")[0]

            # 🚀 FIXED: Decode 'raw_text_bytes' instead of 'raw_data[1:]'
            text_chunk = raw_text_bytes.decode("ascii", errors="replace").strip()
            text_chunk = text_chunk.replace("`", "F").upper()

            # Assign text data straight into its raw hex coordinate position
            self.virtual_screen[lead_byte] = text_chunk
            
            # Real-Time Layout Logger
            print("\n--- Current Virtual Display ---")
            for addr in sorted(self.virtual_screen.keys()):
                print(f"ADDR 0x{addr:02X}: '{self.virtual_screen[addr]}'")
            print("--------------------------------\n")

            # Fire off our upgraded content interpreter
            self._parse_screen_matrix()


    def _parse_screen_matrix(self):
        # Flatten all text segments currently residing in display memory into one block
        status_block = " ".join(self.virtual_screen.values()).upper()

        # Determine if the active frame set represents the Diagnostic Status view
        is_equipment_status = any("EQUIPMENT STATUS" in text for text in self.virtual_screen.values())

        # =====================================================================
        # SCREEN TYPE A: DIAGNOSTIC / EQUIPMENT STATUS PROCESSING
        # =====================================================================
        if is_equipment_status:
            # 1. Parse AquaPure Output Percentage (e.g., "AQUAPURE 40%")
            if "AQUAPURE" in status_block:
                ap_match = re.search(r"AQUAPURE\s*(\d+)\s*%", status_block)
                if ap_match: 
                    self.aquapure_percent = int(ap_match.group(1))

            # 2. Parse SWG Salt Level (e.g., "SALT 3100 PPM")
            if "SALT" in status_block:
                salt_match = re.search(r"SALT\s*(\d+)", status_block)
                if salt_match: 
                    self.salt_ppm = int(salt_match.group(1))

            # 3. Parse Filter Pump Performance Metrics
            # Note: We slice or search flexible numeric groupings to catch trailing anomalies
            if "RPM" in status_block:
                rpm_match = re.search(r"RPM:\s*(\d+)", status_block)
                if rpm_match: 
                    self.filter_rpm = int(rpm_match.group(1))
                    self.filter_pump_on = self.filter_rpm > 0
            elif "FILTER PUMP" in status_block:
                # Fallback flag if pump line is visible but speed info hasn't cycled in yet
                self.filter_pump_on = True

            # 4. Parse Electrical Load draw (e.g., "WATTS: 326")
            if "WATTS" in status_block:
                watts_match = re.search(r"WATTS:\s*(\d+)", status_block)
                if watts_match: 
                    self.filter_watts = int(watts_match.group(1))

            # 5. Global Aux Toggle Monitors
            if "POOL LIGHT" in status_block:
                self.pool_light_on = "POOL LIGHT ON" in status_block
            if "SPA LIGHT" in status_block:
                self.spa_light_on = "SPA LIGHT ON" in status_block

        # =====================================================================
        # SCREEN TYPE B: DYNAMIC MAIN HOME VIEW
        # =====================================================================
        else:
            # Safely fetch known base components or fallback to empty strings
            l2_labels = self.virtual_screen.get(0x01, "")
            l3_values = self.virtual_screen.get(0x82, "")
            l4_footer = self.virtual_screen.get(0x04, "")

            # Air Temperature parsing via index matching
            if "AIR" in l2_labels:
                air_idx = l2_labels.find("AIR")
                air_match = re.search(r"(\d+)\s*F", l3_values[air_idx : air_idx + 10])
                if air_match: 
                    self.air_temp_f = int(air_match.group(1))

            # Pool Temperature tracking
            if "POOL" in l2_labels:
                pool_idx = l2_labels.find("POOL")
                pool_match = re.search(r"(\d+)\s*F", l3_values[pool_idx : pool_idx + 10])
                if pool_match: 
                    self.pool_temp_f = int(pool_match.group(1))

            # Spa Temperature tracking
            if "SPA" in l2_labels:
                spa_idx = l2_labels.find("SPA")
                spa_match = re.search(r"(\d+)\s*F", l3_values[spa_idx : spa_idx + 10])
                if spa_match: 
                    self.spa_temp_f = int(spa_match.group(1))

            # Home-screen operational mode decoders
            if "POOL MODE" in status_block:
                self.mode = PoolMode.POOL if "POOL MODE  ON" in status_block or "POOL MODE ON" in status_block else self.mode
                if "POOL MODE  ON" in status_block or "POOL MODE ON" in status_block:
                    self.filter_pump_on = True
                    
            if "SPA MODE" in status_block:
                self.mode = PoolMode.SPA if "SPA MODE  ON" in status_block or "SPA MODE ON" in status_block else self.mode
                if "SPA MODE  ON" in status_block or "SPA MODE ON" in status_block:
                    self.filter_pump_on = True
                    
            if "ALL OFF" in status_block:
                self.mode = PoolMode.OFF
                self.filter_pump_on = False

    def to_dict(self) -> dict[str, Any]:
        self.check_staleness()
        
        # Convert internal hex coordinate keys to clean string hex keys for JSON compatibility
        export_display = {f"0x{k:02X}": v for k, v in self.virtual_screen.items()}
        
        return {
            "mode": self.mode.value if hasattr(self.mode, 'value') else self.mode,
            "air_temp_f": self.air_temp_f,
            "pool_temp_f": self.pool_temp_f,
            "spa_temp_f": self.spa_temp_f,
            "pool_setpoint_f": self.pool_setpoint_f,
            "spa_setpoint_f": self.spa_setpoint_f,
            
            "salt_ppm": self.salt_ppm,
            "aquapure_percent": self.aquapure_percent,
            "filter_rpm": self.filter_rpm,
            "filter_watts": self.filter_watts,
            
            "filter_pump_on": self.filter_pump_on,
            "aux_pump_on": self.aux_pump_on,
            "heater_on": self.heater_on,
            "pool_light_on": self.pool_light_on,
            "spa_light_on": self.spa_light_on,
            "valve": self.valve,
            "swg_status": self.swg_status,
            "undefined_state": self.undefined_state,
            "last_error": self.last_error,
            "connection_ok": self.connection_ok,
            "last_update": self.last_update,
            "last_packet": dict(self.last_packet) if self.last_packet else {},
            
            "display": export_display
        }
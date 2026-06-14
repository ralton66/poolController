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
        self.swg_percent: int | None = None
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

        # --- ACTION 1: SCREEN WIPE ---
        if dest == 0x60 and cmd == 0x09:
            self.touch()
            self.virtual_screen.clear()
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
            raw_text_bytes = raw_data[1:]
            
            # Drop trailing stale buffer data past null terminators
            if b"\x00" in raw_text_bytes:
                raw_text_bytes = raw_text_bytes.split(b"\x00")[0]

            # Convert to string and clean up Jandy's unique symbols
            text_chunk = raw_text_bytes.decode("ascii", errors="replace").strip()
            text_chunk = text_chunk.replace("`", "F").upper()

            # Store in screen dictionary memory
            self.virtual_screen[lead_byte] = text_chunk
            
            # Trigger main menu parsing ONLY when the definitive final row lands
            if lead_byte == 130:
                print("\n Main Temperature Stream Complete! Parsing home view...")
                for addr in sorted(self.virtual_screen.keys()):
                    print(f"  ADDR 0x{addr:02X} ({addr:03d}): '{self.virtual_screen[addr]}'")
                print("-----------------------------------------------\n")

                self._parse_screen_matrix()
            return

        # --- ACTION 3: PROTOCOL END-OF-SEQUENCE TERMINATOR (0x02) ---
        # The master sends cmd 0x02 right after the last EQUIPMENT STATUS msg_long finishes
        if dest == 0x60 and cmd == 0x02:
            self.touch()
            
            # Only trigger parser if an equipment menu is currently staged in buffer memory
            is_equipment_status = any("EQUIPMENT STATUS" in text for text in self.virtual_screen.values())
            
            if is_equipment_status:
                print("\n Protocol 0x02 Terminator Frame Received! Processing equipment stats...")
                
                # Visual verification printout of exactly what we're handing off
                print("--- Current Staged Equipment Matrix Layout ---")
                for addr in sorted(self.virtual_screen.keys()):
                    print(f"  ADDR 0x{addr:02X} ({addr:03d}): '{self.virtual_screen[addr]}'")
                print("-----------------------------------------------\n")
                
                # Run the interpreter across the complete layout data block
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
                    self.swg_percent = int(ap_match.group(1))

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
            l2_labels = self.virtual_screen.get(0x01, "")
            l3_values = self.virtual_screen.get(0x82, "")  # e.g., "68F     76F"

            if l3_values:
                # 1. Slice the left half of the display buffer for Air Temp
                left_half = l3_values[:8]
                air_match = re.search(r"(\d+)\s*F", left_half)
                if air_match:
                    self.air_temp_f = int(air_match.group(1))

                # 2. Slice the right half of the display buffer for Water Temp
                right_half = l3_values[8:]
                water_match = re.search(r"(\d+)\s*F", right_half)
                
                if water_match:
                    water_temp = int(water_match.group(1))
                    
                    # Check labels context to see if this number belongs to POOL or SPA
                    if "SPA" in l2_labels:
                        self.spa_temp_f = water_temp
                    else:
                        # Default to pool temp if spa mode isn't explicitly on screen
                        self.pool_temp_f = water_temp

            # Home-screen operational mode decoders
            if "POOL MODE" in status_block:
                self.mode = PoolMode.POOL if "POOL MODE  ON" in status_block or "POOL MODE ON" in status_block else self.mode
                if "POOL MODE  ON" in status_block or "POOL MODE ON" in status_block:
                    self.filter_pump_on = True
                    print("PoolMonitor: Pool mode is on, filter pump enabled.")

            if "SPA MODE" in status_block:
                self.mode = PoolMode.SPA if "SPA MODE  ON" in status_block or "SPA MODE ON" in status_block else self.mode
                if "SPA MODE  ON" in status_block or "SPA MODE ON" in status_block:
                    self.filter_pump_on = True
                    print("PoolMonitor: Spa mode is on, filter pump enabled.")
                    
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
            "swg_percent": self.swg_percent,
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

    def cloud_read_dict(self) -> dict[str, Any]:
        """Subset exposed as Cloud read properties (AC-12)."""
        d = self.to_dict()
        return {
            "pool_temp_f": d.get("pool_temp_f"),
            "spa_temp_f": d.get("spa_temp_f"),
            "mode": d.get("mode", "off"),
            "filter_pump_on": d.get("filter_pump_on", False),
            "filter_rpm": d.get("filter_rpm"),
        }

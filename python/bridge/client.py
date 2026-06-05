# SPDX-FileCopyrightText: Copyright (C) ARDUINO SRL (http://www.arduino.cc)
# SPDX-License-Identifier: MPL-2.0

"""Thin Router Bridge helpers for PoolController."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

try:
    from arduino.app_utils import Bridge
except ImportError:
    from app_utils import Bridge

from protocol.jandy_frame import bytes_to_hex, decode_payload, encode_wire, hex_to_bytes

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_LOG = _REPO_ROOT / "protocol.log"


class BridgeClient:
    def __init__(self, log_path: Path | None = None):
        self.log_path = Path(log_path or os.environ.get("PROTOCOL_LOG", _DEFAULT_LOG))

    def send_wire(self, dest: int, cmd: int, data: bytes = b"") -> str:
        """Encode frame on Linux and send full on-wire hex to MCU."""
        print("SW")
        wire = encode_wire(dest, cmd, data)
        hex_wire = bytes_to_hex(wire)
        self._log("TX", hex_wire)
        Bridge.call("RS485_send", hex_wire)
        return hex_wire

    def send_wire_bytes(self, wire: bytes) -> str:
        hex_wire = bytes_to_hex(wire)
        Bridge.notify("RS485_send", hex_wire)
        return hex_wire

    def inject_test_packet(self) -> None:
        """Ask MCU to inject bench RX (sketch test fixture)."""
        Bridge.call("inject_test_packet")

    def log_rx_payload(self, hex_payload: str) -> None:
        csv_line = pda_parse(hex_payload)
        #if hex_payload[:4] in {"0012", "001F", "0020"}:
        #    print("???")
        #elif hex_payload[:2] in {"60", "00"}:
        #    self._log("RX", hex_payload)
        #else if(hex_payload[:2] == "00"):
        self._log("RX", csv_line)

    @staticmethod
    def decode_rx_hex(hex_payload: str):
        payload = hex_to_bytes(hex_payload)
        return decode_payload(payload)

    def _log(self, direction: str, hex_data: str) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        line = f"{ts} {hex_data}\n"
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(line)
        except OSError:
            pass


_client: BridgeClient | None = None


def get_client() -> BridgeClient:
    global _client
    if _client is None:
        _client = BridgeClient()
    return _client

def pda_parse(hex_str):
    # Ensure the string is uppercase and stripped of whitespace
    hex_str = hex_str.strip().upper()
    
    try:
        # Convert the hex string into bytes for easier processing
        packet_bytes = bytes.fromhex(hex_str)
    except ValueError:
        return "ERROR,Invalid Hex String,,,,,"

    if len(packet_bytes) < 3:
        return "ERROR,Packet too short,,,,,"

    # Extract core structural fields
    dest_byte = packet_bytes[0]
    cmd_byte = packet_bytes[1]
    data_bytes = packet_bytes[2:-1]
    checksum_byte = packet_bytes[-1]

    # 1. Determine Direction and Destination Names
    if dest_byte == 0x60:
        direction = "PDA"
        dest_name = " "
    elif dest_byte == 0x00:
        direction = "Mstr"
        dest_name = " "
    else:
        direction = f"0x{dest_byte:02X}"
        dest_name = " "

    # 2. Validate Checksum
    # Sum all bytes except the last one, add 0x10 and 0x02, mask to 1 byte
    calculated_checksum = (sum(packet_bytes[:-1]) + 0x10 + 0x02) & 0xFF
    checksum_status = f"{checksum_byte:02X}" if calculated_checksum == checksum_byte else f"{checksum_byte:02X} (INVALID)"

    # Initialize placeholders for interpretation logic
    parsed_cmd = f"0x{cmd_byte:02X}"
    sub_line = "—"
    interpreted_data = data_bytes.hex().upper()

    # 3. Master to PDA Parsing Logic (Dest 0x60)
    if dest_byte == 0x60:
        if cmd_byte == 0x09:
            parsed_cmd = "CMD_CLR_SCREEN"
            # Keeps the raw data hex string in interpreted_data
        elif cmd_byte == 0x04:
            parsed_cmd = "CMD_MSG_LONG"
            if len(data_bytes) > 0:
                sub_line = f"Line {data_bytes[0]}"
                # Decode the rest of the data payload into ASCII text
                try:
                    interpreted_data = f'"{data_bytes[1:].decode("ascii")}"'
                except UnicodeDecodeError:
                    interpreted_data = f'"{data_bytes[1:].hex().upper()} (Non-ASCII)"'
        elif cmd_byte == 0x08:
            parsed_cmd = "CMD_HIGHLIGHT_LINE"
            if len(data_bytes) > 0:
                sub_line = f"Line {data_bytes[0]}"

    # 4. PDA to Master Parsing Logic (Dest 0x00)
    elif dest_byte == 0x00:
        if cmd_byte == 0x01:
            parsed_cmd = "ACK"
            interpreted_data = "Empty ACK"  # Default fallback if data_bytes is empty
            
            if len(data_bytes) > 0:
                if data_bytes[0] == 0x00:
                    interpreted_data = "ACK"
                elif data_bytes[0] == 0x2C:
                    interpreted_data = "Config Mode Sync"
                elif data_bytes[0] == 0x32:
                    interpreted_data = "Item Sync"
                elif data_bytes[0] == 0x36:
                    interpreted_data = "Line Complete"
                elif data_bytes[0] == 0x41:
                    interpreted_data = "Scr Redraw"
                elif data_bytes[0] == 0x66:
                    interpreted_data = "Matrix Grid Sync"   
                elif data_bytes[0] == 0xBC:
                    interpreted_data = "Hold"
                elif data_bytes[0] == 0xC0:
                    interpreted_data = "Locked"
                elif data_bytes[0] == 0xC4:
                    interpreted_data = "Hardware Processing Lock"
                elif data_bytes[0] == 0x50:
                    key_mapping = {0x00: "None", 0x02: "Back", 0x04: "Select", 0x05: "Down", 0x06: "Up"}
                    
                    if len(data_bytes) > 1:
                        sub_key = data_bytes[1]
                        key_text = key_mapping.get(sub_key, f"Unknown Key (0x{sub_key:02X})")
                    else:
                        key_text = "Missing Key Byte"
                        
                    interpreted_data = f"KEY: {key_text}"
                else:
                    interpreted_data = f"0x{data_bytes.hex().upper()}"

    # 5. Build and return the comma-separated string
    # Format: Dir, Dest, Parsed Command, Sub/Line, Interpreted Data Payload, Checksum
    csv_row = f"{direction},{dest_name},{parsed_cmd},{sub_line},{interpreted_data},{checksum_status},{hex_str}"

    return csv_row
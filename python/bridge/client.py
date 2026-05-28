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
        print("SWB")
        hex_wire = bytes_to_hex(wire)
        hex_wire = "0x10, 0x02, 0x00, 0x01, 0x50, 0x04, 0x67, 0x10, 0x03"
        self._log("TX", hex_wire)
        Bridge.call("RS485_send", hex_wire)
        return hex_wire

    def inject_test_packet(self) -> None:
        """Ask MCU to inject bench RX (sketch test fixture)."""
        Bridge.call("inject_test_packet")

    def log_rx_payload(self, hex_payload: str) -> None:
        self._log("RX", hex_payload)

    @staticmethod
    def decode_rx_hex(hex_payload: str):
        payload = hex_to_bytes(hex_payload)
        return decode_payload(payload)

    def _log(self, direction: str, hex_data: str) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        line = f"{ts} {direction} {hex_data}\n"
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

# SPDX-FileCopyrightText: Copyright (C) ARDUINO SRL (http://www.arduino.cc)
# SPDX-License-Identifier: MPL-2.0

"""High-level pool commands → on-wire Jandy frames (AqualinkD-informed placeholders)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from protocol.jandy_frame import encode_wire

# Panel / AllButton destination used in bench fixtures
DEST_PANEL = 0x00
CMD_STATUS = 0x04


class CommandType(str, Enum):
    SPA_ON = "spa_on"
    POOL_FILTER = "pool_filter"
    ALL_OFF = "all_off"
    LIGHTS = "lights"
    RESET = "reset"
    STATUS_POLL = "status_poll"


@dataclass(frozen=True)
class Command:
    type: CommandType
    temp_f: int | None = None
    rpm: int | None = None
    preset: str | None = None
    lights_on: bool | None = None
    light_target: str = "pool"


def build_wire_frames(cmd: Command) -> list[bytes]:
    """Return ordered on-wire frames for one intent (refine after live protocol.log)."""
    if cmd.type == CommandType.SPA_ON:
        temp = cmd.temp_f if cmd.temp_f is not None else 102
        return [
            _wire(DEST_PANEL, CMD_STATUS, b"SPA MODE"),
            _wire(DEST_PANEL, CMD_STATUS, f"SPA SET {temp}F".encode("ascii")),
        ]
    if cmd.type == CommandType.POOL_FILTER:
        if cmd.rpm is not None:
            data = f"FILTER {cmd.rpm} RPM".encode("ascii")
        elif cmd.preset:
            data = f"FILTER {cmd.preset}".encode("ascii")
        else:
            data = b"FILTER ON"
        return [_wire(DEST_PANEL, CMD_STATUS, data)]
    if cmd.type == CommandType.ALL_OFF:
        return [_wire(DEST_PANEL, CMD_STATUS, b"ALL OFF")]
    if cmd.type == CommandType.LIGHTS:
        target = (cmd.light_target or "pool").upper()
        state = b"ON" if cmd.lights_on else b"OFF"
        return [
            _wire(DEST_PANEL, CMD_STATUS, target.encode("ascii") + b" LIGHT " + state)
        ]
    if cmd.type == CommandType.RESET:
        return [
            _wire(DEST_PANEL, CMD_STATUS, b"AIR TEMP ?"),
            _wire(DEST_PANEL, CMD_STATUS, b"ALL OFF"),
        ]
    if cmd.type == CommandType.STATUS_POLL:
        return [_wire(DEST_PANEL, CMD_STATUS, b"AIR TEMP ?")]
    return []


def _wire(dest: int, cmd: int, data: bytes) -> bytes:
    return encode_wire(dest, cmd, data)

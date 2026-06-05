# SPDX-FileCopyrightText: Copyright (C) ARDUINO SRL (http://www.arduino.cc)
# SPDX-License-Identifier: MPL-2.0

"""PDA / panel message parsing (subset ported from AqualinkD conventions)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .jandy_frame import JandyFrame

# PDA display commands (Jandy protocol)
CMD_PDA_HIGHLIGHT = 0x08
CMD_PDA_CLEAR = 0x09
CMD_PDA_SHIFTLINES = 0x0F
CMD_PDA_HIGHLIGHTCHARS = 0x10
CMD_PDA_0x04 = 0x04
CMD_PDA_0x05 = 0x05
CMD_PDA_0x1B = 0x1B

# Common status text prefixes (panel → bus)
_PREFIXES = (
    "AIR TEMP ",
    "POOL TEMP ",
    "SPA TEMP ",
    "POOL SET ",
    "SPA SET ",
    "FILTER ",
    "PUMP ",
    "HEATER ",
    "LIGHT ",
    "SPA ",
    "POOL ",
    "SALT ",
    "CHLOR ",
)


@dataclass
class ParsedPacket:
    frame: JandyFrame
    text: str | None = None
    label: str | None = None
    value: str | None = None
    fields: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "dest": f"0x{self.frame.dest:02X}",
            "cmd": f"0x{self.frame.cmd:02X}",
            "text": self.text,
            "label": self.label,
            "value": self.value,
            "fields": dict(self.fields),
            "checksum_ok": self.frame.validate_checksum(),
        }


def parse_packet(frame: JandyFrame) -> ParsedPacket:

    parsed = ParsedPacket(frame=frame)
    #print(f"parse_packet: raw frame dest=0x{frame.dest:02X} cmd=0x{frame.cmd:02X} data={frame.data.hex().upper()} checksum=0x{frame.checksum:02X}")
    #if not frame.data:
    #    return parsed

    #try:
    #    text = frame.data.decode("ascii", errors="replace").strip()
    #except Exception:
    #    return parsed

    #if not text:
    #    return parsed
 
    #print(f"parse_packet: D:=0x{parsed.frame.dest:02X} cmd=0x{parsed.frame.cmd:02X} text='{parsed.text}' fields={parsed.fields}") 

    return parsed


def _cmd_name(cmd: int) -> str:
    names = {
        CMD_PDA_0x04: "PDA_0x04",
        CMD_PDA_0x05: "PDA_0x05",
        CMD_PDA_HIGHLIGHT: "PDA_HIGHLIGHT",
        CMD_PDA_CLEAR: "PDA_CLEAR",
        CMD_PDA_SHIFTLINES: "PDA_SHIFTLINES",
        CMD_PDA_HIGHLIGHTCHARS: "PDA_HIGHLIGHTCHARS",
        CMD_PDA_0x1B: "PDA_0x1B",
    }
    return names.get(cmd, f"CMD_0x{cmd:02X}")


def _apply_text_fields(parsed: ParsedPacket, text: str) -> None:
    upper = text.upper()
    for prefix in _PREFIXES:
        if upper.startswith(prefix):
            parsed.label = prefix.strip()
            parsed.value = text[len(prefix) :].strip()
            parsed.fields["kind"] = prefix.strip().lower().replace(" ", "_")
            break

    temp_match = re.match(r"^(AIR|POOL|SPA)\s+TEMP\s+(\d+)\s*F?$", upper)
    if temp_match:
        parsed.fields["temp_type"] = temp_match.group(1).lower()
        parsed.fields["temp_f"] = int(temp_match.group(2))

    set_match = re.match(r"^(POOL|SPA)\s+SET\s+(\d+)\s*F?$", upper)
    if set_match:
        parsed.fields["setpoint_type"] = set_match.group(1).lower()
        parsed.fields["setpoint_f"] = int(set_match.group(2))

    rpm_match = re.search(r"(\d+)\s*RPM", upper)
    if rpm_match:
        parsed.fields["rpm"] = int(rpm_match.group(1))

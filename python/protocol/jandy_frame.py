# SPDX-FileCopyrightText: Copyright (C) ARDUINO SRL (http://www.arduino.cc)
# SPDX-License-Identifier: MPL-2.0

"""Jandy RS485 DLE/STX/ETX framing (AqualinkD-compatible)."""

from __future__ import annotations

from dataclasses import dataclass

DLE = 0x10
STX = 0x02
ETX = 0x03


@dataclass(frozen=True)
class JandyFrame:
    """Decoded frame body: destination, command, data, checksum."""

    dest: int
    cmd: int
    data: bytes
    checksum: int

    @property
    def payload(self) -> bytes:
        """DEST + CMD + DATA (no checksum)."""
        return bytes([self.dest, self.cmd]) + self.data

    def validate_checksum(self) -> bool:
        return checksum8(self.payload + 0x12) == self.checksum
        #return True

def checksum8(body: bytes) -> int:
    return sum(body) & 0xFF

def hex_to_bytes(hex_str: str) -> bytes:
    s = hex_str.strip().replace(" ", "").upper()
    if len(s) % 2:
        raise ValueError("hex string must have even length")
    return bytes.fromhex(s)

def bytes_to_hex(data: bytes) -> str:
    return data.hex().upper()

def encode_wire(dest: int, cmd: int, data: bytes = b"") -> bytes:
    """Build full on-wire frame including DLE/STX/ETX and escapes."""
    body = bytes([dest & 0xFF, cmd & 0xFF]) + data
    body_ck = body + bytes([checksum8(body)])
    out = bytearray([DLE, STX])
    for b in body_ck:
        out.append(b)
        if b == DLE:
            out.append(DLE)
    out.extend([DLE, ETX])
    return bytes(out)

def encode_payload(dest: int, cmd: int, data: bytes = b"") -> bytes:
    """Build frame body only (DEST..CHECKSUM) for Bridge notify / logging."""
    body = bytes([dest & 0xFF, cmd & 0xFF]) + data
    return body + bytes([checksum8(body)])

def decode_wire(frame: bytes) -> JandyFrame:
    """Parse a complete on-wire frame; raises ValueError on failure."""
    if len(frame) < 6:
        raise ValueError("frame too short")
    if frame[0] != DLE or frame[1] != STX:
        raise ValueError("missing DLE STX")
    if frame[-2] != DLE or frame[-1] != ETX:
        raise ValueError("missing DLE ETX")

    body = _unescape(frame[2:-2])
    if len(body) < 3:
        raise ValueError("body too short")
    dest, cmd = body[0], body[1]
    data = body[2:-1]
    cksum = body[-1]
    jf = JandyFrame(dest=dest, cmd=cmd, data=data, checksum=cksum)
    if not jf.validate_checksum():
        raise ValueError("checksum mismatch")
    return jf

def decode_payload(payload: bytes) -> JandyFrame:
    """Parse DEST+CMD+DATA+CHECKSUM (as received from MCU notify)."""
    if len(payload) < 3:
        print("too short")
        raise ValueError("payload too short")
    dest, cmd = payload[0], payload[1]
    data = payload[2:-1]
    cksum = payload[-1]

    jf = JandyFrame(dest=dest, cmd=cmd, data=data, checksum=cksum)
    #if not jf.validate_checksum():
    #    print("cs")
    #    raise ValueError("checksum mismatch")
    return jf

def _unescape(chunk: bytes) -> bytes:
    out = bytearray()
    i = 0
    while i < len(chunk):
        if chunk[i] == DLE and i + 1 < len(chunk) and chunk[i + 1] == DLE:
            out.append(DLE)
            i += 2
        else:
            out.append(chunk[i])
            i += 1
    return bytes(out)

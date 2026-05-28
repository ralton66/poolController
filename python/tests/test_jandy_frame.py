# SPDX-FileCopyrightText: Copyright (C) ARDUINO SRL (http://www.arduino.cc)
# SPDX-License-Identifier: MPL-2.0

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protocol.jandy_frame import (
    bytes_to_hex,
    decode_payload,
    decode_wire,
    encode_payload,
    encode_wire,
    hex_to_bytes,
)
from protocol.pda_messages import parse_packet


class TestJandyFrame(unittest.TestCase):
    def test_mock_air_temp_roundtrip(self):
        data = b"AIR TEMP 75F"
        dest, cmd = 0x08, 0x04
        wire = encode_wire(dest, cmd, data)
        frame = decode_wire(wire)
        self.assertEqual(frame.dest, dest)
        self.assertEqual(frame.cmd, cmd)
        self.assertEqual(frame.data, data)
        self.assertTrue(frame.validate_checksum())

    def test_payload_matches_sketch_notify_format(self):
        data = b"AIR TEMP 75F"
        payload = encode_payload(0x08, 0x04, data)
        hex_payload = bytes_to_hex(payload)
        frame = decode_payload(hex_to_bytes(hex_payload))
        self.assertEqual(frame.data, data)
        parsed = parse_packet(frame)
        self.assertEqual(parsed.fields.get("temp_f"), 75)
        self.assertEqual(parsed.fields.get("temp_type"), "air")

    def test_escape_dle_in_data(self):
        data = bytes([0x10, 0x41])
        wire = encode_wire(0x00, 0x01, data)
        frame = decode_wire(wire)
        self.assertEqual(frame.data, data)


if __name__ == "__main__":
    unittest.main()


# SPDX-FileCopyrightText: Copyright (C) ARDUINO SRL (http://www.arduino.cc)
# SPDX-License-Identifier: MPL-2.0

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from model.pool_state import PoolMode, PoolState
from model.commands import Command, CommandType, build_wire_frames
from protocol.jandy_frame import decode_payload, encode_payload, hex_to_bytes
from protocol.pda_messages import parse_packet


class TestPoolState(unittest.TestCase):
    def test_air_temp_from_fixture(self):
        hex_payload = "08044149522054454D502037354610"
        frame = decode_payload(hex_to_bytes(hex_payload))
        parsed = parse_packet(frame)
        state = PoolState()
        state.apply_parsed(parsed, hex_payload)
        self.assertEqual(state.air_temp_f, 75)
        self.assertTrue(state.connection_ok)

    def test_spa_mode_text(self):
        payload = encode_payload(0x08, 0x04, b"SPA MODE")
        frame = decode_payload(payload)
        parsed = parse_packet(frame)
        state = PoolState()
        state.apply_parsed(parsed)
        self.assertEqual(state.mode, PoolMode.SPA)

    def test_to_dict_keys(self):
        d = PoolState(air_temp_f=70, mode=PoolMode.POOL).to_dict()
        self.assertIn("pool_temp_f", d)
        self.assertEqual(d["mode"], "pool")



if __name__ == "__main__":
    unittest.main()

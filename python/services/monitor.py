# SPDX-FileCopyrightText: Copyright (C) ARDUINO SRL (http://www.arduino.cc)
# SPDX-License-Identifier: MPL-2.0

"""RX path: decode packets and merge into PoolState."""

from __future__ import annotations

import time
import cmd
import threading
from typing import Callable
from enum import Enum
from bridge.client import BridgeClient
from model.pool_state import PoolState
from protocol.jandy_frame import decode_payload, encode_wire, hex_to_bytes
from protocol.pda_messages import parse_packet
from services.controller import PoolController
from model.commands import Command, CommandType, ControlState, StateMachine

class PoolMonitor:
    def __init__(
        self,
        state: PoolState,
        bridge: BridgeClient,
        pc: PoolController,
        sm: StateMachine,
        on_update: Callable[[PoolState], None] | None = None,
         
    ):
        self.state = state
        self.bridge = bridge
        self.pc = pc
        self.sm = sm
        self._on_update = on_update
        self._lock = threading.Lock()

    def handle_hex_payload(self, hex_payload: str) -> None:
        try:
            #self.bridge.log_rx_payload(hex_payload)
            frame = decode_payload(hex_to_bytes(hex_payload))
            parsed = parse_packet(frame)
                
            with self._lock:
                self.state.apply_parsed(parsed, hex_payload)
                self.state.last_error = None
            self._notify()
        except Exception as e:
            with self._lock:
                self.state.last_error = str(e)
                self.state.last_packet = {"error": str(e), "hex": hex_payload}
            self._notify()

    def get_snapshot(self) -> dict:
        with self._lock:
            return self.state.to_dict()

    def _notify(self) -> None:
        if self._on_update:
            self._on_update(self.state)



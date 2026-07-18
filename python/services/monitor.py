# SPDX-FileCopyrightText: Copyright (C) ARDUINO SRL (http://www.arduino.cc)
# SPDX-License-Identifier: MPL-2.0

"""RX path: decode packets and merge into PoolState."""

from __future__ import annotations

import time
import cmd
import threading
from typing import Callable
from enum import Enum
from bridge.client import BridgeClient, Command, CommandType
from model.pool_state import PoolState
from protocol.jandy_frame import decode_payload, encode_wire, hex_to_bytes
from protocol.pda_messages import parse_packet
from services.controller import PoolController
from model.commands import ControlState, StateMachine

UPDATE_SECONDS = 10

class PoolMonitor:
    def __init__(
        self,
        state: PoolState,
        bridge: BridgeClient,
        pc: PoolController,
        on_update: Callable[[PoolState], None] | None = None,
         
    ):
        self.state = state
        self.bridge = bridge
        self.pc = pc
        self.last_update: float = 0.0
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
            
            if(self.state.updated):
                self._notify()

        except Exception as e:
            print("WTF")
            with self._lock:
                self.state.last_error = str(e)
                self.state.last_packet = {"error": str(e), "hex": hex_payload}
            self._notify()

    def get_snapshot(self) -> dict:
        with self._lock:
            return self.state.to_dict()

    def _notify(self) -> None:
        self.connection_ok = True

        update_threshold = UPDATE_SECONDS if 'UPDATE_SECONDS' in globals() else 10
        if time.time() - self.last_update > update_threshold:
            self.last_update = time.time()
            if self._on_update:
                self._on_update(self.state)



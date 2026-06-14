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
            #if frame.dest == 0x60 or frame.dest == 0x00:
            #    self.bridge.log_rx_payload(hex_payload)
            if frame.dest == 0x8880:
                if self.sm.state == ControlState.IDLE:
                    #time to here is critical to respond to master
                    active_cmd = self.check_queue()
                    parsed = parse_packet(frame)
                    if active_cmd is not None:
                        #print("PoolMonitor: Active command found:", active_cmd)
                        self.sm.check_cmd(active_cmd)
                elif self.sm.state == ControlState.SEND_PKTS:
                    #print("PoolMonitor: Received packet in SEND_PKTS state, sending control packets...")
                    wire = self.sm.process_command()
                    #print("PoolMonitor: Sending control packets:", wire.hex().upper())
                    self.bridge.send_wire_bytes(wire)
                elif self.sm.state == ControlState.STATE_RESET:
                    self.pc._queue.task_done()  
                    self.sm.reset_clicks_remaining = self.sm.reset_clicks_total
                    self.sm.state = ControlState.IDLE
                
            with self._lock:
                self.state.apply_parsed(parsed, hex_payload)
                self.state.last_error = None
            self._notify()
            self.bridge.log_rx_payload(hex_payload)
            time.sleep(0.2)
        except Exception as e:
            with self._lock:
                self.state.last_error = str(e)
                self.state.last_packet = {"error": str(e), "hex": hex_payload}
            self._notify()


    def check_queue(self) -> None:
        cmd = None
        try:
            cmd = self.pc._queue.get_nowait()
        except:
            cmd = None
        
        if cmd is not None:
            return cmd       
        else:   

            # Keep Alive Packet
            #PDA_KA = b"\x10\x02\x00\x50\x00\x10\x03"
    
            # Acknowledge Packet
            #PDA_ACK = b"\x10\x02\x00\x01\x50\x00\x63\x10\x03"

            wire = encode_wire(0x00, 0x01, b"\x50\x00") 
            self.bridge.send_wire_bytes(wire)
            #print("PoolMonitor: No command in queue, sent keep-alive packet")
            #time.sleep(0.2)
        return cmd

    def get_snapshot(self) -> dict:
        with self._lock:
            return self.state.to_dict()

    def _notify(self) -> None:
        if self._on_update:
            self._on_update(self.state)



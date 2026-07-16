# SPDX-FileCopyrightText: Copyright (C) ARDUINO SRL (http://www.arduino.cc)
# SPDX-License-Identifier: MPL-2.0

"""High-level pool commands → on-wire Jandy frames (AqualinkD-informed placeholders)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from protocol.jandy_frame import encode_wire

class ControlState(Enum):
    SEND_PKTS = 1
    STATE_RESET = 2
    IDLE = 3

class StateMachine:
    def __init__(
        self,
        state: ControlState,
        timeout_limit: int = 10, 
        reset_clicks: int = 4,
        number_of_packets: int = 0,
        packet_idx: int = 0,
        
    ):
           
        self.state = state
        self.timeout_limit = timeout_limit
        self.reset_clicks_total = reset_clicks
        self.number_of_packets = number_of_packets
        self.packet_idx = packet_idx
        self.reset_clicks_remaining = 0
        self.processed_packets: list[bytes] = []

    #@property
    #def target_line(self) -> int:
        #Helper to get the target line of the current active menu layer.
    #    return self.menu_sequence[self.current_layer_index]

    def check_cmd(self, cmd: Command) -> None:
        self.processed_packets.clear()
        self.number_of_packets = len(cmd.control_packets)
        #print(f"Num packets: {self.number_of_packets}")
        if self.number_of_packets != 0:
            self.packet_idx = 0
            self.state = ControlState.SEND_PKTS
            for index, packet in enumerate(cmd.control_packets, start=1):
                self.processed_packets.append(packet)
                #print(f"Processing packet {index}/{self.number_of_packets}: {packet.hex().upper()} Bytes: {self.processed_packets[index-1]}")
        else:
            print(f"Received command has no packets. {cmd.control_packets[0] if cmd.control_packets else 'No packets'}")


    def process_command(self) -> None:
        #print(f"Processing command Num:{self.number_of_packets} Idx: {self.packet_idx} Pkt: {self.processed_packets[self.packet_idx]}")
        if self.number_of_packets == (self.packet_idx + 1):    
            self.state = ControlState.STATE_RESET
        
        self.packet_idx += 1
        return self.processed_packets[self.packet_idx-1]
       

def _wire(dest: int, cmd: int, data: bytes) -> bytes:
    return encode_wire(dest, cmd, data)

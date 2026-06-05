# SPDX-FileCopyrightText: Copyright (C) ARDUINO SRL (http://www.arduino.cc)
# SPDX-License-Identifier: MPL-2.0

"""RX path: decode packets and merge into PoolState."""

from __future__ import annotations

import threading
from typing import Callable

from bridge.client import BridgeClient
from model.pool_state import PoolState
from protocol.jandy_frame import decode_payload, encode_wire, hex_to_bytes
from protocol.pda_messages import parse_packet
from services.controller import PoolController
from model.commands import Command, CommandType, build_wire_frames

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
        self._on_update = on_update
        self._lock = threading.Lock()

    def handle_hex_payload(self, hex_payload: str) -> None:
        try:
            self.bridge.log_rx_payload(hex_payload)
            frame = decode_payload(hex_to_bytes(hex_payload))
            parsed = parse_packet(frame)
            if frame.dest == 96:
                self.check_queue()
            
        except Exception as e:
            with self._lock:
                self.state.last_error = str(e)
                self.state.last_packet = {"error": str(e), "hex": hex_payload}
            self._notify()
            # add update code back in here
    def check_queue(self) -> None:

        cmd = None
        try:
            cmd = self.pc._queue.get_nowait()
        except:
            cmd = None
        
        if cmd is not None:
            wire = encode_wire(0x00, 0x01, b"\x50\x05")
            self.pc._queue.task_done()         
        else:   
            wire = encode_wire(0x00, 0x01, b"\x00\x00") 
        self.bridge.send_wire_bytes(wire)


    def get_snapshot(self) -> dict:
        with self._lock:
            return self.state.to_dict()

    def _notify(self) -> None:
        if self._on_update:
            self._on_update(self.state)


"""

class JandyPDAStateMachine:
    def __init__(self, menu_sequence: list, timeout_limit: int = 10, reset_clicks: int = 4):
      
        :param menu_sequence: List of integers representing the target line for each menu layer.
                              Example: [4] for just line 4, or [2, 4] for line 2 then line 4.
        :param timeout_limit: Number of packets to wait for confirmation in the final state.
        :param reset_clicks: Number of ACK_BACK commands to send during a timeout reset.
        """

"""

        if not menu_sequence:
            raise ValueError("menu_sequence must contain at least one target line layer.")
            
        self.menu_sequence = menu_sequence
        self.current_layer_index = 0  # Tracks which menu level we are currently navigating
        
        self.state = PDAState.NAVIGATING_LAYERS
        self.current_line = None
        
        # Timeout and recovery configurations
        self.timeout_limit = timeout_limit
        self.reset_clicks_total = reset_clicks
        self.packet_counter = 0
        self.reset_clicks_remaining = 0
        
        # logging.info(f"State Machine Initialized. Layers to process: {len(self.menu_sequence)} | Sequence: {self.menu_sequence}")

    @property
    def target_line(self) -> int:
        #Helper to get the target line of the current active menu layer.
        return self.menu_sequence[self.current_layer_index]

    def process_packet(self, packet_type: str, payload: dict) -> str:
        
        #Processes an incoming packet from the master and returns the next action/command to send.
        
        action = "ACK_NONE"

        # --- STATE: NAVIGATING LAYERS (Dynamic Menu Traversal) ---
        if self.state == PDAState.NAVIGATING_LAYERS:
            # Step A: Parse status packets to figure out where we are
            if packet_type == "STATUS" and "highlighted_line" in payload:
                # If we didn't know the line yet, this packet anchors us
                is_initial_fish = self.current_line is None
                self.current_line = payload["highlighted_line"]
                
                logging.info(f"[Layer {self.current_layer_index}] Current line: {self.current_line} (Target: {self.target_line})")
                
                # If the line is verified to match our target for this layer, select it
                if self.current_line == self.target_line:
                    logging.info(f"[Layer {self.current_layer_index}] Target line {self.target_line} reached! Sending SELECT.")
                    action = "ACK_SELECT"
                    
                    # Wipe line context for the next screen layer since the menu will change
                    self.current_line = None 
                    
                    # Advance to next layer or proceed to final confirmation phase
                    if self.current_layer_index < len(self.menu_sequence) - 1:
                        self.current_layer_index += 1
                        logging.info(f"Advancing to next sub-menu. Now managing Layer Index {self.current_layer_index}.")
                    else:
                        self.state = PDAState.CONFIRM_PUMP
                        self.packet_counter = 0
                        logging.info("All layers navigated. Transitioning to CONFIRM_PUMP.")
                else:
                    # If we didn't know the line before this packet, we just sent a blind DOWN. 
                    # Now that we know the line, calculate the next corrective action.
                    action = self._calculate_navigation_action()
            else:
                # If no status packet is received yet or we don't know our line, fish for it
                action = "ACK_DOWN"

        # --- STATE: CONFIRM PUMP IS ON (WITH TIMEOUT) ---
        elif self.state == PDAState.CONFIRM_PUMP:
            self.packet_counter += 1
            logging.info(f"[Confirm Phase] Received packet {self.packet_counter}/{self.timeout_limit}")

            if packet_type == "LONG_MESSAGE" and "text" in payload:
                message_text = payload["text"].upper()
                if "FILTER PUMP ON" in message_text:
                    logging.info("[Confirm Phase] 'FILTER PUMP ON' detected!")
                    self.state = PDAState.IDLE
                    logging.info("Transitioning to IDLE. Task Complete.")
                    return "ACK_NONE"

            if self.packet_counter >= self.timeout_limit:
                logging.warning(f"[Confirm Phase] Timeout! ({self.timeout_limit} packets without confirmation)")
                self.state = PDAState.STATE_RESET
                self.reset_clicks_remaining = self.reset_clicks_total
                logging.info(f"Transitioning to STATE_RESET. Will issue {self.reset_clicks_remaining} BACK commands.")
                
                action = "ACK_BACK"
                self.reset_clicks_remaining -= 1
            else:
                action = "ACK_NONE"

        # --- STATE: RESET RECOVERY ---
        elif self.state == PDAState.STATE_RESET:
            if self.reset_clicks_remaining > 0:
                logging.info(f"[State Reset] Sending BACK keypress. Remaining: {self.reset_clicks_remaining}")
                action = "ACK_BACK"
                self.reset_clicks_remaining -= 1
            else:
                logging.info("[State Reset] Finished resetting. Restarting entire menu sequence from Layer 0.")
                self.current_layer_index = 0
                self.current_line = None
                self.state = PDAState.NAVIGATING_LAYERS
                action = "ACK_DOWN"

        # --- IDLE STATE ---
        elif self.state == PDAState.IDLE:
            action = "ACK_NONE"

        return action

    def _calculate_navigation_action(self) -> str:
        if self.current_line is None:
            return "ACK_DOWN"
        if self.current_line < self.target_line:
            return "ACK_DOWN"
        elif self.current_line > self.target_line:
            return "ACK_UP"
        return "ACK_NONE"


# ==========================================
# SIMULATION / MULTI-LAYER DEMONSTRATION
# ==========================================
#if __name__ == "__main__":
#    # Example: 2 layers deep. Menu 1 target line is 4. Sub-menu target line is 2.
#    target_sequence = [4, 2]

"""
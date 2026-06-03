# SPDX-FileCopyrightText: Copyright (C) ARDUINO SRL (http://www.arduino.cc)
# SPDX-License-Identifier: MPL-2.0

"""Serialized command queue → RS485 TX."""

from __future__ import annotations

import queue
import threading
import time
from typing import Callable

from bridge.client import BridgeClient
from model.commands import Command, CommandType, build_wire_frames
from model.pool_state import PoolState

FRAME_GAP_S = 0.35


class PoolController:
    def __init__(
        self,
        bridge: BridgeClient,
        state: PoolState | None = None,
        on_tx: Callable[[str], None] | None = None,
    ):
        self.bridge = bridge
        self.state = state
        self._on_tx = on_tx
        self._queue: queue.Queue[Command | None] = queue.Queue()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._running = False

    def start(self) -> None:
        if not self._running:
            self._running = True
            self._thread.start()

    def stop(self) -> None:
        self._running = False
        self._queue.put(None)

    def enqueue(self, cmd: Command) -> None:
        self._queue.put(cmd)

    def spa_on(self, temp_f: int) -> None:
        self.enqueue(Command(type=CommandType.SPA_ON, temp_f=temp_f))

    def pool_filter(self, rpm: int | None = None, preset: str | None = None) -> None:
        self.enqueue(
            Command(type=CommandType.POOL_FILTER, rpm=rpm, preset=preset)
        )

    def all_off(self) -> None:
        self.enqueue(Command(type=CommandType.ALL_OFF))

    def set_lights(self, on: bool, target: str = "pool") -> None:
        self.enqueue(
            Command(
                type=CommandType.LIGHTS,
                lights_on=on,
                light_target=target,
            )
        )

    def reset(self) -> None:
        self.enqueue(Command(type=CommandType.RESET))

    def _worker(self) -> None:
        while self._running:
            try:
                cmd = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if cmd is None:
                break
            self._execute(cmd)
            if self.state and self.state.undefined_state and cmd.type != CommandType.RESET:
                self.enqueue(Command(type=CommandType.RESET))

    def _execute(self, cmd: Command) -> None:
        for wire in build_wire_frames(cmd):
            hex_wire = self.bridge.send_wire_bytes(wire)
            if self._on_tx:
                self._on_tx(hex_wire)
            time.sleep(FRAME_GAP_S)



from enum import Enum, auto

class PDAState(Enum):
    IDLE = auto()
    STATE_1_GET_LINE = auto()       # Send DOWN to find initial highlighted line
    STATE_2_NAVIGATE = auto()       # Send UP/DOWN until line 4 is highlighted
    STATE_3_SELECT = auto()         # Send SELECT key to toggle pump
    STATE_4_CONFIRM_PUMP = auto()   # Wait for "FILTER PUMP ON" confirmation

class JandyPDAStateMachine:
    def __init__(self):
        self.state = PDAState.STATE_1_GET_LINE
        self.current_line = None
        self.target_line = 4
        logging.info("State Machine Initialized. Starting at STATE_1_GET_LINE.")

    def process_packet(self, packet_type: str, payload: dict) -> str:
        """
        Processes an incoming packet from the master and returns the next action/command to send.
        
        :param packet_type: Type of packet ('STATUS', 'LONG_MESSAGE', etc.)
        :param payload: Dict containing parsed packet data (e.g., {'highlighted_line': 2, 'text': '...'})
        :return: String command to send back to the master (e.g., 'ACK_DOWN', 'ACK_SELECT', 'ACK_NONE')
        """
        action = "ACK_NONE"  # Default response

        # --- STATE 1: DETERMINE INITIAL LINE ---
        if self.state == PDAState.STATE_1_GET_LINE:
            # We need to fish for the highlighted line by sending a DOWN press
            action = "ACK_DOWN"
            
            if packet_type == "STATUS" and "highlighted_line" in payload:
                self.current_line = payload["highlighted_line"]
                logging.info(f"[State 1] Highlighted line detected: {self.current_line}")
                
                # Transition to navigation state
                self.state = PDAState.STATE_2_NAVIGATE
                logging.info(f"Transitioning to STATE_2_NAVIGATE. Target: Line {self.target_line}")
                
                # Immediately evaluate navigation for the next loop
                action = self._calculate_navigation_action()

        # --- STATE 2: NAVIGATE TO LINE 4 ---
        elif self.state == PDAState.STATE_2_NAVIGATE:
            if packet_type == "STATUS" and "highlighted_line" in payload:
                self.current_line = payload["highlighted_line"]
                logging.info(f"[State 2] Current highlighted line: {self.current_line}")
                
                if self.current_line == self.target_line:
                    logging.info(f"[State 2] Target line {self.target_line} reached!")
                    self.state = PDAState.STATE_3_SELECT
                    logging.info("Transitioning to STATE_3_SELECT.")
                    action = "ACK_SELECT"
                else:
                    action = self._calculate_navigation_action()

        # --- STATE 3: SELECT/TOGGLE PUMP ---
        elif self.state == PDAState.STATE_3_SELECT:
            # We stay here briefly to issue the select command. 
            # Once sent, we move to the confirmation phase.
            logging.info("[State 3] Sending SELECT keypress to turn on filter pump.")
            action = "ACK_SELECT"
            self.state = PDAState.STATE_4_CONFIRM_PUMP
            logging.info("Transitioning to STATE_4_CONFIRM_PUMP.")

        # --- STATE 4: CONFIRM PUMP IS ON ---
        elif self.state == PDAState.STATE_4_CONFIRM_PUMP:
            if packet_type == "LONG_MESSAGE" and "text" in payload:
                message_text = payload["text"].upper()
                logging.info(f"[State 4] Received message: '{message_text}'")
                
                if "FILTER PUMP ON" in message_text:
                    logging.info("[State 4] Confirmation received! 'FILTER PUMP ON' detected.")
                    self.state = PDAState.IDLE
                    logging.info("Transitioning to IDLE. Task Complete.")
            
            # Keep sending standard ACKs while waiting to maintain connection protocol
            action = "ACK_NONE" 

        # --- IDLE STATE ---
        elif self.state == PDAState.IDLE:
            action = "ACK_NONE"

        return action

    def _calculate_navigation_action(self) -> str:
        """Helper to decide whether to move UP or DOWN to hit line 4."""
        if self.current_line is None:
            return "ACK_DOWN"
        
        if self.current_line < self.target_line:
            logging.info(f"Target is below current line. Moving DOWN.")
            return "ACK_DOWN"
        elif self.current_line > self.target_line:
            logging.info(f"Target is above current line. Moving UP.")
            return "ACK_UP"
        
        return "ACK_NONE"

# ==========================================
# SIMULATION / EXAMPLE USAGE
# ==========================================
if __name__ == "__main__":
    pda = JandyPDAStateMachine()

    # Simulated stream of messages from the Jandy Master
    simulated_packets = [
        # State 1: We don't know the line, master sends a status packet, we reply DOWN
        ("STATUS", {"highlighted_line": 2}), 
        
        # State 2: Master processes the DOWN, sends updated status (line 2 now known)
        ("STATUS", {"highlighted_line": 2}), 
        
        # State 2: Master moves down to line 3
        ("STATUS", {"highlighted_line": 3}), 
        
        # State 2: Master moves down to line 4 (Target hit!)
        ("STATUS", {"highlighted_line": 4}), 
        
        # State 3: Select packet is sent. Master processes it and returns display text update
        ("LONG_MESSAGE", {"text": "Executing command..."}),
        
        # State 4: Master broadcasts the target string
        ("LONG_MESSAGE", {"text": "FILTER PUMP ON"}),
    ]

    print("\n--- Starting Simulation ---")
    for i, (p_type, payload) in enumerate(simulated_packets, 1):
        print(f"\n[Packet #{i} Inbound] Type: {p_type}, Data: {payload}")
        response = pda.process_packet(p_type, payload)
        print(f"[Response Outbound] -> {response}")
    print("\n--- Simulation Finished ---")
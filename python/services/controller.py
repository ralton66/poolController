# SPDX-FileCopyrightText: Copyright (C) ARDUINO SRL (http://www.arduino.cc)
# SPDX-License-Identifier: MPL-2.0

"""Serialized command queue → RS485 TX."""

from __future__ import annotations

import queue
import threading
import time
from typing import Callable
from bridge.client import BridgeClient, Command, CommandType
from model.pool_state import PoolMode, PoolState

FRAME_GAP_S = 1

class ControlPackets:
    """Steady-State Operational Ready Packets (Answering normal runtime loops)"""
    
    # Keep Alive Packet
    PDA_KA = b"\x10\x02\x00\x01\x00\x00\x13\x10\x03"
    
    # Acknowledge Packet
    PDA_ACK = b"\x10\x02\x00\x01\x50\x00\x63\x10\x03"
    
    # Check Status / Checksum Packet
    PDA_CS = b"\x10\x02\x00\x20\x46\x00\x00\x00\x00\x48\x10\x03"
    
    # Handshake Packet
    PDA_HS = b"\x10\x02\x00\x20\x46\x00\x00\x03\x30\x32\x30\x00\x00\x3D\x10\x03"
    
    # Select Packet
    PDA_SELECT = b"\x10\x02\x00\x01\x50\x04\x67\x10\x03"

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

    def pool_filter(self) -> None:
        print("PoolController: pool_filter called")
        self.enqueue(Command(command_type=CommandType.POOL_FILTER))

    def pool_filter_rpm(self, rpm: int | None = None) -> None:
        print("PoolController: pool_filter called")
        self.enqueue(Command(command_type=CommandType.POOL_FILTER_RPM, rpm=rpm))
    
    def pool_heater(self) -> None:
        print("PoolController: pool_heater called")
        self.enqueue(Command(command_type=CommandType.POOL_HEATER))
    
    def pool_temp(self, temp_f: int) -> None:
        self.enqueue(Command(command_type=CommandType.POOL_TEMP, temp_f=temp_f))

    def spa_on(self) -> None:
        print("PoolController: spa_on called")
        self.enqueue(Command(command_type=CommandType.SPA_ON))

    def spa_heater(self) -> None:
        print("PoolController: spa_heater called")
        self.enqueue(Command(command_type=CommandType.SPA_HEATER))

    def spa_temp(self, temp_f: int) -> None:
        self.enqueue(Command(command_type=CommandType.SPA_TEMP, temp_f=temp_f))

    def jets(self) -> None:
        print("PoolController: jets called")
        self.enqueue(Command(command_type=CommandType.JETS))

    def all_off(self) -> None:
        print("PoolController: all_off called")
        self.enqueue(Command(command_type=CommandType.ALL_OFF))
    
    def pda(self) -> None:
        print("PoolController: PDA called")
        self.enqueue(Command(command_type=CommandType.PDA))

    def set_pool_lights(self) -> None:
        print("PoolController: set_pool_lights called")
        self.enqueue( Command(command_type=CommandType.POOL_LIGHTS))

    def set_spa_lights(self) -> None:
        print("PoolController: set_spa_lights called")
        self.enqueue( Command(command_type=CommandType.SPA_LIGHTS))

    def reset(self) -> None:
        print("PoolController: reset called")
        #self.enqueue(Command(type=CommandType.RESET))

    def _worker(self) -> None:
        while self._running:
            try:
                cmd = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            
            time.sleep(FRAME_GAP_S)
            if cmd is None:
                break
            self._execute(cmd)
            if self.state and self.state.undefined_state and cmd.type != CommandType.RESET:
                self.enqueue(Command(type=CommandType.RESET))

    def _execute(self, cmd: Command) -> None:
        print("controller: _execute (command type:)", cmd.type)
        self.bridge.control_command(cmd)






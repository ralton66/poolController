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

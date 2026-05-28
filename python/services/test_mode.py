# SPDX-FileCopyrightText: Copyright (C) ARDUINO SRL (http://www.arduino.cc)
# SPDX-License-Identifier: MPL-2.0

"""Test mode: fixture replay and TCP inject for AC-9/AC-10."""

from __future__ import annotations

import json
import os
import socketserver
import threading
from pathlib import Path

from services.monitor import PoolMonitor

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_FIXTURES = _REPO_ROOT / "test" / "fixtures"
_DEFAULT_PORT = 19555


def is_test_mode() -> bool:
    return os.environ.get("POOL_TEST_MODE", "0") == "1"


def test_port() -> int:
    return int(os.environ.get("POOL_TEST_PORT", str(_DEFAULT_PORT)))


def fixtures_dir() -> Path:
    return Path(os.environ.get("POOL_TEST_FIXTURES", str(_DEFAULT_FIXTURES)))


class TestModeService:
    def __init__(self, monitor: PoolMonitor):
        self.monitor = monitor
        self._server: socketserver.ThreadingTCPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not is_test_mode():
            return
        self.load_fixtures_on_startup()
        self._thread = threading.Thread(target=self._run_tcp_server, daemon=True)
        self._thread.start()

    def load_fixtures_on_startup(self) -> None:
        if os.environ.get("POOL_TEST_AUTO_FIXTURES", "1") != "1":
            return
        for path in sorted(fixtures_dir().glob("*.hex")):
            self._inject_file(path)

    def inject_hex(self, hex_payload: str) -> None:
        hex_payload = hex_payload.strip().replace(" ", "").upper()
        self.monitor.handle_hex_payload(hex_payload)

    def _inject_file(self, path: Path) -> None:
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            self.inject_hex(line)

    def _run_tcp_server(self) -> None:
        monitor = self.monitor
        port = test_port()

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                for raw in self.rfile:
                    line = raw.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                    except json.JSONDecodeError:
                        self.wfile.write(
                            json.dumps({"ok": False, "error": "invalid json"}).encode()
                            + b"\n"
                        )
                        continue
                    mtype = msg.get("type")
                    if mtype == "inject":
                        hex_val = msg.get("hex", "")
                        monitor.handle_hex_payload(hex_val)
                        self.wfile.write(
                            json.dumps({"ok": True, "type": "inject"}).encode() + b"\n"
                        )
                    elif mtype == "ping":
                        self.wfile.write(
                            json.dumps({"ok": True, "type": "pong"}).encode() + b"\n"
                        )
                    else:
                        self.wfile.write(
                            json.dumps(
                                {"ok": False, "error": f"unknown type {mtype}"}
                            ).encode()
                            + b"\n"
                        )

        self._server = socketserver.ThreadingTCPServer(
            ("0.0.0.0", port), Handler
        )
        self._server.allow_reuse_address = True
        print(f"POOL_TEST_MODE: TCP inject on port {port}")
        self._server.serve_forever()

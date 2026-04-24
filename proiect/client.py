#!/usr/bin/env python3
"""
Test client for the proxy server.

ProxyClient connects to the proxy and exposes:
  - send(dest_host, dest_port, operation, data)  — fire-and-forget
  - wait(count, timeout)                          — block until N responses arrive
  - close()                                       — tear down the connection

A background receiver thread collects responses and prints them as they arrive,
allowing multiple concurrent requests to be sent without blocking.
"""

import json
import os
import socket
import threading
import time

PROXY_HOST = os.environ.get('PROXY_HOST', 'localhost')
PROXY_PORT = int(os.environ.get('PROXY_PORT', 9000))


def _send(sock: socket.socket, obj: dict) -> None:
    sock.sendall((json.dumps(obj) + '\n').encode('utf-8'))


class ProxyClient:
    def __init__(self, name: str = 'Client',
                 host: str = PROXY_HOST, port: int = PROXY_PORT):
        self.name = name
        self.host = host
        self.port = port
        self._sock: socket.socket | None = None
        self._responses: list = []
        self._lock = threading.Lock()
        self._reader: threading.Thread | None = None

    # ── Connection ───────────────────────────────────────────────────────────

    def connect(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.connect((self.host, self.port))
        self._reader = threading.Thread(target=self._recv_loop, daemon=True)
        self._reader.start()
        print(f"[{self.name}] Connected to proxy {self.host}:{self.port}")

    def _recv_loop(self) -> None:
        sock_file = self._sock.makefile('r', encoding='utf-8')
        try:
            for raw in sock_file:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    resp = json.loads(raw)
                except json.JSONDecodeError:
                    print(f"[{self.name}] Malformed response: {raw!r}")
                    continue
                rid = resp.get('request_id', '?')
                status = resp.get('status', '?')
                result = resp.get('result', '')
                print(
                    f"[{self.name}] ← id={rid[:8]}…  "
                    f"status={status}  result={result!r}"
                )
                with self._lock:
                    self._responses.append(resp)
        except OSError:
            pass
        finally:
            sock_file.close()

    # ── Sending ──────────────────────────────────────────────────────────────

    def send(self, dest_host: str, dest_port: int,
             operation: str, data: str = '') -> None:
        req = {
            'destination_host': dest_host,
            'destination_port': dest_port,
            'operation': operation,
            'data': data,
        }
        print(
            f"[{self.name}] → {operation!r} → {dest_host}:{dest_port}  "
            f"data={data!r:.40}"
        )
        _send(self._sock, req)

    # ── Receiving ────────────────────────────────────────────────────────────

    def wait(self, count: int, timeout: float = 15.0) -> list:
        """Block until at least `count` responses have arrived or timeout expires."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                if len(self._responses) >= count:
                    return list(self._responses)
            time.sleep(0.05)
        with self._lock:
            return list(self._responses)

    # ── Teardown ─────────────────────────────────────────────────────────────

    def close(self) -> None:
        try:
            self._sock.close()
        except OSError:
            pass


# ── Standalone usage ─────────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys

    dest_host = os.environ.get('DEST_HOST', 'localhost')
    dest_port = int(os.environ.get('DEST_PORT', 9001))

    client = ProxyClient('CLI')
    client.connect()

    if len(sys.argv) == 3:
        client.send(dest_host, dest_port, sys.argv[1], sys.argv[2])
        client.wait(1, timeout=10)
    else:
        # Default: echo two messages concurrently
        client.send(dest_host, dest_port, 'echo', 'hello from client')
        client.send(dest_host, dest_port, 'echo', 'second message')
        client.wait(2, timeout=10)

    time.sleep(0.2)
    client.close()

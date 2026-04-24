#!/usr/bin/env python3
"""
Destination server.

Receives requests from the proxy, processes them (possibly with an artificial
delay for out-of-order demonstrations), and always includes the original
request_id in the response so the proxy can route it back to the right client.

Each request is handled in its own thread so slow_echo does not block
other concurrent requests on the same connection.
"""

import json
import logging
import os
import socket
import threading
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [DEST] %(levelname)s %(message)s',
)

DEST_HOST = '0.0.0.0'
DEST_PORT = int(os.environ.get('DEST_PORT', 9001))
SERVER_FILES_DIR = os.environ.get('SERVER_FILES_DIR', 'server_files')

os.makedirs(SERVER_FILES_DIR, exist_ok=True)


# ── I/O ──────────────────────────────────────────────────────────────────────

def _send(sock: socket.socket, obj: dict) -> None:
    sock.sendall((json.dumps(obj) + '\n').encode('utf-8'))


# ── Operation dispatch ───────────────────────────────────────────────────────

def _process(request_id: str, operation: str, data: str) -> dict:
    try:
        if operation == 'echo':
            return {'request_id': request_id, 'status': 'ok', 'result': data}

        if operation == 'slow_echo':
            # data: JSON {"message": "...", "delay": <seconds>}
            payload = json.loads(data)
            delay = float(payload.get('delay', 2))
            message = payload.get('message', '')
            time.sleep(delay)
            return {'request_id': request_id, 'status': 'ok',
                    'result': f'[after {delay}s] {message}'}

        if operation == 'read_file':
            path = os.path.join(SERVER_FILES_DIR, os.path.basename(data))
            with open(path) as fh:
                return {'request_id': request_id, 'status': 'ok', 'result': fh.read()}

        if operation == 'write_file':
            payload = json.loads(data)
            path = os.path.join(SERVER_FILES_DIR, os.path.basename(payload['filename']))
            with open(path, 'w') as fh:
                fh.write(payload['content'])
            return {'request_id': request_id, 'status': 'ok',
                    'result': f"written: {payload['filename']}"}

        return {'request_id': request_id, 'status': 'error',
                'result': f'unknown operation: {operation}'}

    except FileNotFoundError:
        return {'request_id': request_id, 'status': 'error', 'result': 'file not found'}
    except Exception as exc:
        return {'request_id': request_id, 'status': 'error', 'result': str(exc)}


# ── Proxy-connection handler ──────────────────────────────────────────────────

def _handle_proxy(proxy_sock: socket.socket, addr: tuple) -> None:
    """
    Reads a stream of requests from the proxy and spawns a worker thread
    per request.  A write_lock ensures responses from concurrent workers
    do not interleave on the socket.
    """
    logging.info(f"Proxy connected: {addr}")
    write_lock = threading.Lock()
    sock_file = proxy_sock.makefile('r', encoding='utf-8')

    def _worker(request_id: str, operation: str, data: str) -> None:
        response = _process(request_id, operation, data)
        logging.info(f"Responding to {operation!r} (id={request_id[:8]}…)")
        try:
            with write_lock:
                _send(proxy_sock, response)
        except OSError as exc:
            logging.warning(f"Cannot send response for {request_id[:8]}…: {exc}")

    try:
        for raw in sock_file:
            raw = raw.strip()
            if not raw:
                continue
            try:
                req = json.loads(raw)
            except json.JSONDecodeError:
                logging.warning(f"Malformed JSON from proxy: {raw!r}")
                continue

            request_id = req.get('request_id', '')
            operation = req.get('operation', '')
            data = req.get('data', '')

            if not request_id or not operation:
                logging.warning("Request missing request_id or operation — skipping")
                continue

            logging.info(f"Received {operation!r} (id={request_id[:8]}…) from {addr}")
            threading.Thread(
                target=_worker, args=(request_id, operation, data), daemon=True
            ).start()

    except OSError:
        pass
    finally:
        sock_file.close()
        proxy_sock.close()
        logging.info(f"Proxy disconnected: {addr}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((DEST_HOST, DEST_PORT))
    server.listen(128)
    logging.info(
        f"Destination server listening on {DEST_HOST}:{DEST_PORT}  "
        f"|  files: {SERVER_FILES_DIR}/"
    )

    try:
        while True:
            proxy_sock, addr = server.accept()
            threading.Thread(
                target=_handle_proxy, args=(proxy_sock, addr), daemon=True
            ).start()
    except KeyboardInterrupt:
        logging.info("Shutting down destination server")
    finally:
        server.close()


if __name__ == '__main__':
    main()

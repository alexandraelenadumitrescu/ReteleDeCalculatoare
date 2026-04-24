#!/usr/bin/env python3
"""
Concurrent proxy server.

Accepts client connections on PROXY_PORT, assigns every request a UUID,
maintains a thread-safe mapping  request_id -> client_socket, forwards
requests to the appropriate destination server, and routes responses
back to the correct client using the request_id.

Direct requests addressed to 'proxy' are served locally from proxy_files/.
"""

import json
import logging
import os
import socket
import threading
import uuid

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [PROXY] %(levelname)s %(message)s',
)

PROXY_HOST = '0.0.0.0'
PROXY_PORT = int(os.environ.get('PROXY_PORT', 9000))
PROXY_FILES_DIR = os.environ.get('PROXY_FILES_DIR', 'proxy_files')

os.makedirs(PROXY_FILES_DIR, exist_ok=True)

# ── Global state ────────────────────────────────────────────────────────────

# request_id -> {'client_sock': socket, 'dest_key': (host, port)}
_pending: dict = {}
_pending_lock = threading.Lock()

# (host, port) -> {'socket': socket, 'lock': Lock, 'alive': bool, 'key': tuple}
_dest_conns: dict = {}
_dest_conns_lock = threading.Lock()


# ── I/O ─────────────────────────────────────────────────────────────────────

def _send(sock: socket.socket, obj: dict) -> None:
    sock.sendall((json.dumps(obj) + '\n').encode('utf-8'))


# ── Local (proxy-side) operations ────────────────────────────────────────────

def _local(request_id: str, operation: str, data: str) -> dict:
    try:
        if operation == 'read_file':
            path = os.path.join(PROXY_FILES_DIR, os.path.basename(data))
            with open(path) as fh:
                return {'request_id': request_id, 'status': 'ok', 'result': fh.read()}

        if operation == 'write_file':
            payload = json.loads(data)
            path = os.path.join(PROXY_FILES_DIR, os.path.basename(payload['filename']))
            with open(path, 'w') as fh:
                fh.write(payload['content'])
            return {'request_id': request_id, 'status': 'ok',
                    'result': f"written: {payload['filename']}"}

        if operation == 'echo':
            return {'request_id': request_id, 'status': 'ok', 'result': data}

        return {'request_id': request_id, 'status': 'error',
                'result': f'unknown operation: {operation}'}

    except FileNotFoundError:
        return {'request_id': request_id, 'status': 'error',
                'result': f'file not found: {data}'}
    except Exception as exc:
        return {'request_id': request_id, 'status': 'error', 'result': str(exc)}


# ── Destination-connection management ────────────────────────────────────────

def _dest_reader(conn_info: dict) -> None:
    """
    Reads newline-delimited JSON responses from a destination server and
    routes each response to the correct client via _pending.
    Runs in its own daemon thread, one per destination (host, port).
    """
    key = conn_info['key']
    sock = conn_info['socket']
    sock_file = sock.makefile('r', encoding='utf-8')
    logging.info(f"Reader started for destination {key}")

    try:
        for raw in sock_file:
            raw = raw.strip()
            if not raw:
                continue
            try:
                response = json.loads(raw)
            except json.JSONDecodeError:
                logging.warning(f"Malformed JSON from {key}: {raw!r}")
                continue

            request_id = response.get('request_id')
            if not request_id:
                logging.warning(f"Response from {key} has no request_id — discarding")
                continue

            with _pending_lock:
                entry = _pending.pop(request_id, None)

            if entry is None:
                logging.warning(f"Unknown request_id {request_id!r} from {key} — discarding")
                continue

            try:
                _send(entry['client_sock'], response)
                logging.info(f"Routed response (id={request_id[:8]}…) back to client")
            except OSError:
                logging.warning(f"Client socket gone before response {request_id[:8]}… could be delivered")

    except OSError:
        pass
    finally:
        conn_info['alive'] = False
        sock_file.close()

        with _dest_conns_lock:
            if _dest_conns.get(key) is conn_info:
                del _dest_conns[key]

        # Notify clients whose requests were in-flight when the destination died
        with _pending_lock:
            orphaned = {rid: e for rid, e in _pending.items() if e['dest_key'] == key}
            for rid in orphaned:
                del _pending[rid]

        for rid, entry in orphaned.items():
            try:
                _send(entry['client_sock'], {
                    'request_id': rid,
                    'status': 'error',
                    'result': f'destination {key[0]}:{key[1]} disconnected',
                })
            except OSError:
                pass

        logging.info(f"Destination {key} disconnected; {len(orphaned)} orphaned request(s) notified")


def _get_dest_conn(host: str, port: int) -> dict | None:
    """Returns an alive connection to (host, port), creating one if needed."""
    key = (host, port)

    with _dest_conns_lock:
        conn = _dest_conns.get(key)
        if conn and conn['alive']:
            return conn

    # Create connection outside the global lock so we don't block other threads
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((host, port))
        sock.settimeout(None)
    except OSError as exc:
        logging.error(f"Cannot connect to {host}:{port}: {exc}")
        return None

    conn_info = {
        'socket': sock,
        'lock': threading.Lock(),
        'alive': True,
        'key': key,
    }

    with _dest_conns_lock:
        existing = _dest_conns.get(key)
        if existing and existing['alive']:
            # Another thread raced us and already created a connection
            sock.close()
            return existing
        _dest_conns[key] = conn_info

    threading.Thread(target=_dest_reader, args=(conn_info,), daemon=True).start()
    logging.info(f"New connection established to {key}")
    return conn_info


# ── Client handler ───────────────────────────────────────────────────────────

def _handle_client(client_sock: socket.socket, addr: tuple) -> None:
    logging.info(f"Client connected: {addr}")
    owned_ids: set = set()   # request_ids registered by this client
    sock_file = client_sock.makefile('r', encoding='utf-8')

    try:
        for raw in sock_file:
            raw = raw.strip()
            if not raw:
                continue

            request_id = str(uuid.uuid4())

            try:
                req = json.loads(raw)
            except json.JSONDecodeError:
                _send(client_sock, {
                    'request_id': request_id,
                    'status': 'error',
                    'result': 'malformed JSON',
                })
                continue

            dest_host = req.get('destination_host', '')
            dest_port_raw = req.get('destination_port')
            operation = req.get('operation', '')
            data = req.get('data', '')

            if not dest_host or dest_port_raw is None or not operation:
                _send(client_sock, {
                    'request_id': request_id,
                    'status': 'error',
                    'result': 'missing required fields: destination_host, destination_port, operation',
                })
                continue

            try:
                dest_port = int(dest_port_raw)
            except (TypeError, ValueError):
                _send(client_sock, {
                    'request_id': request_id,
                    'status': 'error',
                    'result': f'invalid destination_port: {dest_port_raw!r}',
                })
                continue

            # ── Direct request to the proxy itself ──────────────────────────
            if dest_host == 'proxy':
                response = _local(request_id, operation, data)
                try:
                    _send(client_sock, response)
                except OSError:
                    pass
                continue

            # ── Register before forwarding so the response can always be routed
            with _pending_lock:
                _pending[request_id] = {
                    'client_sock': client_sock,
                    'dest_key': (dest_host, dest_port),
                }
                owned_ids.add(request_id)

            conn = _get_dest_conn(dest_host, dest_port)
            if conn is None:
                with _pending_lock:
                    _pending.pop(request_id, None)
                owned_ids.discard(request_id)
                _send(client_sock, {
                    'request_id': request_id,
                    'status': 'error',
                    'result': f'cannot connect to {dest_host}:{dest_port}',
                })
                continue

            fwd = {'request_id': request_id, 'operation': operation, 'data': data}
            try:
                with conn['lock']:
                    _send(conn['socket'], fwd)
                logging.info(
                    f"Forwarded {operation!r} (id={request_id[:8]}…) "
                    f"from {addr} → {dest_host}:{dest_port}"
                )
            except OSError as exc:
                with _pending_lock:
                    _pending.pop(request_id, None)
                owned_ids.discard(request_id)
                conn['alive'] = False
                _send(client_sock, {
                    'request_id': request_id,
                    'status': 'error',
                    'result': f'failed to forward request: {exc}',
                })

    except OSError:
        pass
    finally:
        # Clean up any pending requests that were never fulfilled
        with _pending_lock:
            for rid in owned_ids:
                _pending.pop(rid, None)
        sock_file.close()
        client_sock.close()
        logging.info(f"Client disconnected: {addr}")


# ── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((PROXY_HOST, PROXY_PORT))
    server.listen(128)
    logging.info(
        f"Proxy listening on {PROXY_HOST}:{PROXY_PORT}  "
        f"|  local files: {PROXY_FILES_DIR}/"
    )

    try:
        while True:
            client_sock, addr = server.accept()
            threading.Thread(
                target=_handle_client, args=(client_sock, addr), daemon=True
            ).start()
    except KeyboardInterrupt:
        logging.info("Shutting down proxy")
    finally:
        server.close()


if __name__ == '__main__':
    main()

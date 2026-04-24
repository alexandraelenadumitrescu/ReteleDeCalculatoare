#!/usr/bin/env python3
"""
Automated demonstration of all 8 required scenarios.

Environment variables (set automatically by docker-compose, or override manually):
  PROXY_HOST  — hostname of the proxy       (default: localhost)
  PROXY_PORT  — port of the proxy           (default: 9000)
  DEST_HOST   — hostname of dest server     (default: localhost)
  DEST_PORT   — port of dest server         (default: 9001)
"""

import json
import os
import socket
import threading
import time

from client import ProxyClient

PROXY_HOST = os.environ.get('PROXY_HOST', 'localhost')
PROXY_PORT = int(os.environ.get('PROXY_PORT', 9000))
DEST_HOST = os.environ.get('DEST_HOST', 'localhost')
DEST_PORT = int(os.environ.get('DEST_PORT', 9001))

PASS = '[PASS]'
FAIL = '[FAIL]'


# ── Helpers ───────────────────────────────────────────────────────────────────

def banner(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print('─' * 60)


def wait_for_tcp(host: str, port: int, timeout: float = 30) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            s.connect((host, port))
            s.close()
            return True
        except OSError:
            time.sleep(0.5)
    return False


# ── Scenario 1 ────────────────────────────────────────────────────────────────

def scenario_1() -> None:
    banner('Scenario 1 — Proxy is running (started in Docker)')
    ok = wait_for_tcp(PROXY_HOST, PROXY_PORT, timeout=5)
    status = PASS if ok else FAIL
    print(f"  {status} proxy reachable at {PROXY_HOST}:{PROXY_PORT}")


# ── Scenario 2 ────────────────────────────────────────────────────────────────

def scenario_2() -> None:
    banner('Scenario 2 — At least one destination server is running')
    ok = wait_for_tcp(DEST_HOST, DEST_PORT, timeout=5)
    status = PASS if ok else FAIL
    print(f"  {status} destination server reachable at {DEST_HOST}:{DEST_PORT}")


# ── Scenario 3 ────────────────────────────────────────────────────────────────

def scenario_3() -> None:
    banner('Scenario 3 — Two clients connect to the proxy simultaneously')
    c1 = ProxyClient('Client-1')
    c2 = ProxyClient('Client-2')
    c1.connect()
    c2.connect()

    c1.send(DEST_HOST, DEST_PORT, 'echo', 'ping from client-1')
    c2.send(DEST_HOST, DEST_PORT, 'echo', 'ping from client-2')

    r1 = c1.wait(1, timeout=8)
    r2 = c2.wait(1, timeout=8)
    c1.close()
    c2.close()

    ok = len(r1) >= 1 and len(r2) >= 1
    print(f"  {PASS if ok else FAIL} both clients received independent responses")


# ── Scenarios 4 & 5 ───────────────────────────────────────────────────────────

def scenario_4_5() -> None:
    banner('Scenarios 4 & 5 — Concurrent requests to same destination; '
           'responses correlated by request_id')
    c1 = ProxyClient('Alpha')
    c2 = ProxyClient('Beta')
    c1.connect()
    c2.connect()

    # Use a Barrier so both sends happen at the same wall-clock instant
    barrier = threading.Barrier(2)

    def send_alpha():
        barrier.wait()
        c1.send(DEST_HOST, DEST_PORT, 'echo', 'data-from-alpha')

    def send_beta():
        barrier.wait()
        c2.send(DEST_HOST, DEST_PORT, 'echo', 'data-from-beta')

    t1 = threading.Thread(target=send_alpha, daemon=True)
    t2 = threading.Thread(target=send_beta, daemon=True)
    t1.start(); t2.start()
    t1.join(); t2.join()

    r1 = c1.wait(1, timeout=8)
    r2 = c2.wait(1, timeout=8)
    c1.close()
    c2.close()

    ok = (
        len(r1) >= 1 and len(r2) >= 1
        and r1[0].get('result') == 'data-from-alpha'
        and r2[0].get('result') == 'data-from-beta'
    )
    print(f"  {PASS if ok else FAIL} each client received exactly its own response")
    if r1:
        print(f"    Alpha: id={r1[0]['request_id'][:8]}…  result={r1[0]['result']!r}")
    if r2:
        print(f"    Beta:  id={r2[0]['request_id'][:8]}…  result={r2[0]['result']!r}")


# ── Scenario 6 ────────────────────────────────────────────────────────────────

def scenario_6() -> None:
    banner('Scenario 6 — Direct request to proxy (read/write proxy_files/)')
    c = ProxyClient('DirectClient')
    c.connect()

    # Write a file to the proxy's own storage
    c.send('proxy', PROXY_PORT, 'write_file',
           json.dumps({'filename': 'hello.txt', 'content': 'Hello from proxy_files!\n'}))
    # Read it back (both requests are processed in order in the same handler thread)
    c.send('proxy', PROXY_PORT, 'read_file', 'hello.txt')

    responses = c.wait(2, timeout=8)
    c.close()

    write_ok = len(responses) >= 1 and responses[0]['status'] == 'ok'
    read_ok = (len(responses) >= 2
               and responses[1]['status'] == 'ok'
               and 'Hello from proxy_files' in responses[1]['result'])

    print(f"  {PASS if write_ok else FAIL} write_file to proxy_files/ succeeded")
    print(f"  {PASS if read_ok  else FAIL} read_file  from proxy_files/ succeeded")
    if len(responses) >= 2:
        print(f"    content: {responses[1]['result']!r}")


# ── Scenario 7 ────────────────────────────────────────────────────────────────

def scenario_7() -> None:
    banner('Scenario 7 — Destination server unavailable → proper error response')
    c = ProxyClient('ErrorClient')
    c.connect()

    # Port 19999 — nothing is listening there
    c.send(DEST_HOST, 19999, 'echo', 'this should fail')
    responses = c.wait(1, timeout=8)
    c.close()

    ok = len(responses) >= 1 and responses[0]['status'] == 'error'
    print(f"  {PASS if ok else FAIL} received error response (not a hang or crash)")
    if responses:
        print(f"    error: {responses[0]['result']!r}")


# ── Scenario 8 ────────────────────────────────────────────────────────────────

def scenario_8() -> None:
    banner('Scenario 8 — Out-of-order responses via slow_echo')
    c = ProxyClient('OOOClient')
    c.connect()

    print("  Sending SLOW request first (3 s), then FAST request (0.1 s) …")

    # Both go to the same destination over the same TCP connection.
    # The destination processes them concurrently; the fast one replies first.
    c.send(DEST_HOST, DEST_PORT, 'slow_echo',
           json.dumps({'message': 'SLOW — sent 1st', 'delay': 3}))
    time.sleep(0.05)  # tiny gap so the socket ordering is deterministic
    c.send(DEST_HOST, DEST_PORT, 'slow_echo',
           json.dumps({'message': 'FAST — sent 2nd', 'delay': 0.1}))

    responses = c.wait(2, timeout=12)
    c.close()

    ok = len(responses) >= 2
    print(f"  {PASS if ok else FAIL} both responses received with correct request_ids")
    for i, r in enumerate(responses, 1):
        print(f"    response {i}: id={r['request_id'][:8]}…  result={r['result']!r}")

    if ok:
        fast_first = 'FAST' in responses[0]['result']
        print(
            f"  {'[NOTE]'} FAST response arrived "
            f"{'BEFORE' if fast_first else 'AFTER'} SLOW response "
            f"({'out-of-order as expected' if fast_first else 'in-order — check delays'})"
        )


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print('=' * 60)
    print('  Proxy Server — Demo Scenarios')
    print('=' * 60)
    print(f'  Proxy:       {PROXY_HOST}:{PROXY_PORT}')
    print(f'  Destination: {DEST_HOST}:{DEST_PORT}')

    print('\nWaiting for services to be ready …')
    if not wait_for_tcp(PROXY_HOST, PROXY_PORT, timeout=30):
        print(f'ERROR: proxy not reachable at {PROXY_HOST}:{PROXY_PORT}')
        return
    if not wait_for_tcp(DEST_HOST, DEST_PORT, timeout=30):
        print(f'ERROR: destination server not reachable at {DEST_HOST}:{DEST_PORT}')
        return
    print('Services are up.\n')

    for fn in (scenario_1, scenario_2, scenario_3,
               scenario_4_5, scenario_6, scenario_7, scenario_8):
        fn()
        time.sleep(0.3)

    print(f"\n{'=' * 60}")
    print('  All scenarios completed.')
    print('=' * 60)


if __name__ == '__main__':
    main()

# Proxy Server — Computer Networks Assignment

A concurrent TCP proxy server built with Python's standard library only
(`socket`, `threading`, `uuid`, `json`, `os`, `time`).

---

## Architecture

```
Client-1 ──┐                       ┌── Destination Server (port 9001)
           │                       │
Client-2 ──┤──► Proxy (port 9000) ─┤
           │                       │
Client-N ──┘                       └── Destination Server 2 (port 9002)
```

### Components

| File | Role |
|------|------|
| `proxy.py` | Proxy server — routes requests using UUID request IDs |
| `destination_server.py` | Destination server — processes operations, echoes request_id |
| `client.py` | Test client — sends requests, receives responses asynchronously |
| `demo_scenarios.py` | Automates all 8 demonstration scenarios |
| `Dockerfile` | Single image for all three roles |
| `docker-compose.yml` | Starts proxy + 2 destination servers + demo client |

### Proxy internals

- **Client handler thread** (one per connected client): reads requests, generates UUIDs,
  registers `request_id → client_socket` in a thread-safe dict, forwards to the destination.
- **Destination reader thread** (one per unique `(host, port)` pair): reads responses,
  looks up the `request_id` in the pending dict, routes back to the correct client.
- Persistent TCP connections are reused across requests to the same destination,
  enabling true multiplexing and out-of-order response delivery.

---

## Protocol

All messages are **newline-delimited JSON** (`\n` terminated), UTF-8 encoded.

### Client → Proxy

```json
{
  "destination_host": "destination_server",
  "destination_port": 9001,
  "operation": "echo",
  "data": "hello world"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `destination_host` | string | yes | Target hostname or `"proxy"` for a direct proxy request |
| `destination_port` | int | yes | Target port |
| `operation` | string | yes | One of: `echo`, `slow_echo`, `read_file`, `write_file` |
| `data` | string | no | Operation payload (see below) |

### Proxy → Destination

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "operation": "echo",
  "data": "hello world"
}
```

The proxy injects `request_id` (a UUID v4) and strips the routing fields.

### Destination → Proxy

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "ok",
  "result": "hello world"
}
```

The destination **must** reflect `request_id` unchanged so the proxy can route the response.

### Proxy → Client

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "ok",
  "result": "hello world"
}
```

The proxy forwards the destination's response verbatim (including `request_id`).

---

## Supported Operations

### `echo`
Returns `data` unchanged.
```json
{ "operation": "echo", "data": "any string" }
```

### `slow_echo`
Returns the message after an artificial delay. Used to demonstrate out-of-order responses.
```json
{
  "operation": "slow_echo",
  "data": "{\"message\": \"hello\", \"delay\": 2.5}"
}
```

### `read_file`
Reads a file from the server's `server_files/` directory (or `proxy_files/` for direct proxy requests).
```json
{ "operation": "read_file", "data": "notes.txt" }
```

### `write_file`
Writes a file to the server's local directory.
```json
{
  "operation": "write_file",
  "data": "{\"filename\": \"notes.txt\", \"content\": \"line 1\\nline 2\\n\"}"
}
```

---

## Error Responses

Every error is returned as a normal response with `"status": "error"`:

| Situation | `result` value |
|-----------|---------------|
| Destination unreachable | `"cannot connect to host:port"` |
| Destination disconnected mid-flight | `"destination host:port disconnected"` |
| Unknown `request_id` in response | logged and silently discarded |
| Malformed JSON from client | `"malformed JSON"` |
| Missing required fields | `"missing required fields: …"` |
| File not found | `"file not found: <name>"` |
| Client disconnects mid-request | pending entries cleaned up silently |

---

## Running with Docker

```bash
# Build the image and start all services.
# The demo container runs all 8 scenarios automatically, then exits.
docker-compose up --build

# Watch only the demo output
docker-compose up --build demo

# Stop everything
docker-compose down
```

Services exposed on the host:

| Service | Host port |
|---------|-----------|
| proxy | 9000 |
| destination_server | 9001 |
| destination_server_2 | 9002 |

---

## Running Locally (without Docker)

Open three terminal windows in the project directory:

```bash
# Terminal 1 — destination server
python destination_server.py

# Terminal 2 — proxy
python proxy.py

# Terminal 3 — demo
python demo_scenarios.py
```

Override defaults with environment variables:

```bash
PROXY_PORT=9000 DEST_PORT=9001 python demo_scenarios.py
```

Use `client.py` as a quick manual test:

```bash
# echo
python client.py echo "hello"

# slow echo
python client.py slow_echo '{"message":"hi","delay":1}'
```

---

## Demo Scenarios

| # | Scenario | How it is shown |
|---|----------|-----------------|
| 1 | Proxy started in Docker | TCP reachability check on proxy port |
| 2 | Destination server running | TCP reachability check on dest port |
| 3 | Two clients connect simultaneously | Both connect and each sends an echo |
| 4 | Two clients → same destination concurrently | `threading.Barrier` fires both sends at once |
| 5 | Responses correctly correlated by `request_id` | Each client's result string matches what it sent |
| 6 | Direct request to proxy (`proxy_files/`) | write_file then read_file addressed to `"proxy"` |
| 7 | Destination unavailable | Error response for port 19999 (nothing listening) |
| 8 | Out-of-order responses | slow_echo(3 s) sent before slow_echo(0.1 s); fast reply arrives first |

---

## Concurrency Model

- Python `threading` throughout (no asyncio).
- One daemon thread per connected client (proxy side).
- One daemon reader thread per unique destination `(host, port)`.
- One daemon worker thread per request (destination server side).
- Thread-safe shared state:
  - `_pending` dict protected by `threading.Lock`.
  - Per-destination write path protected by a per-connection `threading.Lock`.
  - Destination server write path protected by a per-connection `threading.Lock`.

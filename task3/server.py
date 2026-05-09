import socket
import threading
import json
import os
import struct
import base64
from datetime import datetime

HOST = "127.0.0.1"
PORT = 9999
FILES_DIR = "files"
USERS = {"student": "1234"}

file_history = {}
history_lock = threading.Lock()


def ensure_dirs():
    os.makedirs(FILES_DIR, exist_ok=True)


def send_message(conn, data):
    msg = json.dumps(data).encode("utf-8")
    conn.sendall(struct.pack(">I", len(msg)) + msg)


def recv_all(conn, n):
    data = b""
    while len(data) < n:
        chunk = conn.recv(n - len(data))
        if not chunk:
            return None
        data += chunk
    return data


def recv_message(conn):
    raw_len = recv_all(conn, 4)
    if not raw_len:
        return None
    msg_len = struct.unpack(">I", raw_len)[0]
    data = recv_all(conn, msg_len)
    if not data:
        return None
    return json.loads(data.decode("utf-8"))


def add_history(filename, operation):
    with history_lock:
        if filename not in file_history:
            file_history[filename] = []
        file_history[filename].append({
            "operation": operation,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })


def handle_client(conn, addr):
    print(f"[SERVER] New connection from {addr}")
    authenticated = False

    try:
        while True:
            msg = recv_message(conn)
            if msg is None:
                break

            command = msg.get("command")
            print(f"[SERVER] [{addr}] Command: {command}")

            if command == "login":
                user = msg.get("username")
                pwd = msg.get("password")
                if USERS.get(user) == pwd:
                    authenticated = True
                    send_message(conn, {"status": "ok", "message": f"Welcome, {user}!"})
                else:
                    send_message(conn, {"status": "error", "message": "Invalid credentials."})

            elif command == "logout":
                send_message(conn, {"status": "ok", "message": "Goodbye!"})
                break

            elif not authenticated:
                send_message(conn, {"status": "error", "message": "Not authenticated."})

            elif command == "list_files":
                files = os.listdir(FILES_DIR)
                send_message(conn, {"status": "ok", "files": files})

            elif command == "create_file":
                filename = msg.get("filename")
                content = msg.get("content", "")
                filepath = os.path.join(FILES_DIR, filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
                add_history(filename, "create")
                send_message(conn, {"status": "ok", "message": f"File '{filename}' created."})

            elif command == "upload":
                filename = msg.get("filename")
                content_b64 = msg.get("content", "")
                content = base64.b64decode(content_b64)
                filepath = os.path.join(FILES_DIR, filename)
                with open(filepath, "wb") as f:
                    f.write(content)
                add_history(filename, "upload")
                send_message(conn, {"status": "ok", "message": f"File '{filename}' uploaded."})

            elif command == "rename_file":
                old_name = msg.get("old_name")
                new_name = msg.get("new_name")
                old_path = os.path.join(FILES_DIR, old_name)
                new_path = os.path.join(FILES_DIR, new_name)
                if not os.path.exists(old_path):
                    send_message(conn, {"status": "error", "message": f"File '{old_name}' not found."})
                elif os.path.exists(new_path):
                    send_message(conn, {"status": "error", "message": f"File '{new_name}' already exists."})
                else:
                    os.rename(old_path, new_path)
                    with history_lock:
                        if old_name in file_history:
                            file_history[new_name] = file_history.pop(old_name)
                    add_history(new_name, f"renamed from '{old_name}'")
                    send_message(conn, {"status": "ok", "message": f"File renamed to '{new_name}'."})

            elif command == "read_file":
                filename = msg.get("filename")
                filepath = os.path.join(FILES_DIR, filename)
                if not os.path.exists(filepath):
                    send_message(conn, {"status": "error", "message": f"File '{filename}' not found."})
                else:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                    add_history(filename, "read")
                    send_message(conn, {"status": "ok", "content": content})

            elif command == "download":
                filename = msg.get("filename")
                filepath = os.path.join(FILES_DIR, filename)
                if not os.path.exists(filepath):
                    send_message(conn, {"status": "error", "message": f"File '{filename}' not found."})
                else:
                    with open(filepath, "rb") as f:
                        content_b64 = base64.b64encode(f.read()).decode("utf-8")
                    add_history(filename, "download")
                    send_message(conn, {"status": "ok", "filename": filename, "content": content_b64})

            elif command == "edit_file":
                filename = msg.get("filename")
                content = msg.get("content", "")
                filepath = os.path.join(FILES_DIR, filename)
                if not os.path.exists(filepath):
                    send_message(conn, {"status": "error", "message": f"File '{filename}' not found."})
                else:
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(content)
                    add_history(filename, "edit")
                    send_message(conn, {"status": "ok", "message": f"File '{filename}' updated."})

            elif command == "see_file_operation_history":
                filename = msg.get("filename")
                with history_lock:
                    history = list(file_history.get(filename, []))
                send_message(conn, {"status": "ok", "history": history})

            else:
                send_message(conn, {"status": "error", "message": f"Unknown command: '{command}'"})

    except Exception as e:
        print(f"[SERVER] Error with {addr}: {e}")
    finally:
        conn.close()
        print(f"[SERVER] Connection closed: {addr}")


def start_server():
    ensure_dirs()
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(5)
    print(f"[SERVER] FTP Server listening on {HOST}:{PORT}")
    print(f"[SERVER] Serving files from: {os.path.abspath(FILES_DIR)}/")

    try:
        while True:
            conn, addr = server.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print("[SERVER] Shutting down...")
    finally:
        server.close()


if __name__ == "__main__":
    start_server()

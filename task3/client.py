import socket
import json
import os
import struct
import base64

HOST = "127.0.0.1"
PORT = 9999
LOCAL_FILES_DIR = "local_files"

sock = None


def ensure_dirs():
    os.makedirs(LOCAL_FILES_DIR, exist_ok=True)


def send_message(data):
    msg = json.dumps(data).encode("utf-8")
    sock.sendall(struct.pack(">I", len(msg)) + msg)


def recv_all(n):
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            return None
        data += chunk
    return data


def recv_message():
    raw_len = recv_all(4)
    if not raw_len:
        return None
    msg_len = struct.unpack(">I", raw_len)[0]
    data = recv_all(msg_len)
    if not data:
        return None
    return json.loads(data.decode("utf-8"))


def connect():
    global sock
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((HOST, PORT))
    print(f"[CLIENT] Connected to {HOST}:{PORT}")


def login():
    username = input("Username: ").strip()
    password = input("Password: ").strip()
    send_message({"command": "login", "username": username, "password": password})
    resp = recv_message()
    if resp and resp.get("status") == "ok":
        print(f"[SERVER] {resp.get('message')}")
        return True
    print(f"[SERVER] {resp.get('message') if resp else 'No response'}")
    return False


def create_file():
    name = input("File name (without extension): ").strip()
    ext = input("Extension (e.g. txt, py): ").strip()
    print("Enter content (type END on a new line to finish):")
    lines = []
    while True:
        line = input()
        if line == "END":
            break
        lines.append(line)
    content = "\n".join(lines)
    filename = f"{name}.{ext}"
    filepath = os.path.join(LOCAL_FILES_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[CLIENT] File '{filename}' created in '{LOCAL_FILES_DIR}/'.")


def upload():
    files = os.listdir(LOCAL_FILES_DIR)
    if not files:
        print("[CLIENT] No local files to upload.")
        return
    print("Local files:")
    for i, f in enumerate(files):
        print(f"  {i + 1}. {f}")
    choice = input("Select file number: ").strip()
    try:
        filename = files[int(choice) - 1]
    except (ValueError, IndexError):
        print("[CLIENT] Invalid selection.")
        return
    filepath = os.path.join(LOCAL_FILES_DIR, filename)
    with open(filepath, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode("utf-8")
    send_message({"command": "upload", "filename": filename, "content": content_b64})
    resp = recv_message()
    print(f"[SERVER] {resp.get('message') if resp else 'No response'}")


def rename_file():
    old_name = input("Current filename (with extension): ").strip()
    new_name = input("New filename (with extension): ").strip()
    send_message({"command": "rename_file", "old_name": old_name, "new_name": new_name})
    resp = recv_message()
    print(f"[SERVER] {resp.get('message') if resp else 'No response'}")


def read_file():
    send_message({"command": "list_files"})
    resp = recv_message()
    if not resp or resp.get("status") != "ok":
        print("[CLIENT] Could not retrieve file list.")
        return
    files = resp.get("files", [])
    if not files:
        print("[CLIENT] No files on server.")
        return
    print("Server files:")
    for i, f in enumerate(files):
        print(f"  {i + 1}. {f}")
    choice = input("Select file number: ").strip()
    try:
        filename = files[int(choice) - 1]
    except (ValueError, IndexError):
        print("[CLIENT] Invalid selection.")
        return
    send_message({"command": "read_file", "filename": filename})
    resp = recv_message()
    if resp and resp.get("status") == "ok":
        print(f"\n--- Content of '{filename}' ---")
        print(resp.get("content"))
        print("--- End of file ---\n")
    else:
        print(f"[SERVER] {resp.get('message') if resp else 'No response'}")


def download():
    send_message({"command": "list_files"})
    resp = recv_message()
    if not resp or resp.get("status") != "ok":
        print("[CLIENT] Could not retrieve file list.")
        return
    files = resp.get("files", [])
    if not files:
        print("[CLIENT] No files on server.")
        return
    print("Server files:")
    for i, f in enumerate(files):
        print(f"  {i + 1}. {f}")
    choice = input("Select file number: ").strip()
    try:
        filename = files[int(choice) - 1]
    except (ValueError, IndexError):
        print("[CLIENT] Invalid selection.")
        return
    send_message({"command": "download", "filename": filename})
    resp = recv_message()
    if resp and resp.get("status") == "ok":
        content = base64.b64decode(resp.get("content", ""))
        save_path = os.path.join(LOCAL_FILES_DIR, resp.get("filename", filename))
        with open(save_path, "wb") as f:
            f.write(content)
        print(f"[CLIENT] File '{filename}' saved to '{LOCAL_FILES_DIR}/'.")
    else:
        print(f"[SERVER] {resp.get('message') if resp else 'No response'}")


def edit_file():
    send_message({"command": "list_files"})
    resp = recv_message()
    if not resp or resp.get("status") != "ok":
        print("[CLIENT] Could not retrieve file list.")
        return
    files = resp.get("files", [])
    if not files:
        print("[CLIENT] No files on server.")
        return
    print("Server files:")
    for i, f in enumerate(files):
        print(f"  {i + 1}. {f}")
    choice = input("Select file number: ").strip()
    try:
        filename = files[int(choice) - 1]
    except (ValueError, IndexError):
        print("[CLIENT] Invalid selection.")
        return
    print("Enter new content (type END on a new line to finish):")
    lines = []
    while True:
        line = input()
        if line == "END":
            break
        lines.append(line)
    content = "\n".join(lines)
    send_message({"command": "edit_file", "filename": filename, "content": content})
    resp = recv_message()
    print(f"[SERVER] {resp.get('message') if resp else 'No response'}")


def see_file_operation_history():
    send_message({"command": "list_files"})
    resp = recv_message()
    if not resp or resp.get("status") != "ok":
        print("[CLIENT] Could not retrieve file list.")
        return
    files = resp.get("files", [])
    if not files:
        print("[CLIENT] No files on server.")
        return
    print("Server files:")
    for i, f in enumerate(files):
        print(f"  {i + 1}. {f}")
    choice = input("Select file number: ").strip()
    try:
        filename = files[int(choice) - 1]
    except (ValueError, IndexError):
        print("[CLIENT] Invalid selection.")
        return
    send_message({"command": "see_file_operation_history", "filename": filename})
    resp = recv_message()
    if resp and resp.get("status") == "ok":
        history = resp.get("history", [])
        if not history:
            print(f"[CLIENT] No history recorded for '{filename}'.")
        else:
            print(f"\n--- Operation history for '{filename}' ---")
            for entry in history:
                print(f"  [{entry['timestamp']}] {entry['operation']}")
            print("--- End of history ---\n")
    else:
        print(f"[SERVER] {resp.get('message') if resp else 'No response'}")


def list_files():
    send_message({"command": "list_files"})
    resp = recv_message()
    if resp and resp.get("status") == "ok":
        files = resp.get("files", [])
        if not files:
            print("[CLIENT] No files on server.")
        else:
            print("Files on server:")
            for f in files:
                print(f"  - {f}")
    else:
        print(f"[SERVER] {resp.get('message') if resp else 'No response'}")


def logout():
    send_message({"command": "logout"})
    resp = recv_message()
    print(f"[SERVER] {resp.get('message') if resp else 'No response'}")


def disconnect():
    global sock
    if sock:
        sock.close()
        sock = None
    print("[CLIENT] Disconnected.")


def menu():
    while True:
        print("\n=== FTP Client Menu ===")
        print("1. Create file (local)")
        print("2. Upload file to server")
        print("3. Rename file on server")
        print("4. Read file from server")
        print("5. Download file from server")
        print("6. Edit file on server")
        print("7. See file operation history")
        print("8. List files on server")
        print("9. Logout & exit")
        choice = input("Choice: ").strip()

        if choice == "1":
            create_file()
        elif choice == "2":
            upload()
        elif choice == "3":
            rename_file()
        elif choice == "4":
            read_file()
        elif choice == "5":
            download()
        elif choice == "6":
            edit_file()
        elif choice == "7":
            see_file_operation_history()
        elif choice == "8":
            list_files()
        elif choice == "9":
            logout()
            break
        else:
            print("[CLIENT] Invalid choice.")


def main():
    ensure_dirs()
    connect()
    if login():
        menu()
    disconnect()


if __name__ == "__main__":
    main()

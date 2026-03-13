import socket
import threading

HOST = "127.0.0.1"
PORT = 3333
BUFFER_SIZE = 1024

class State:
    def __init__(self):
        self.data = {}
        self.lock = threading.Lock()

    def add(self, key, value):
        with self.lock:
            self.data[key] = value
        return "OK - record add"

    def get(self, key):
        with self.lock:
            if key in self.data:
                return f"DATA {self.data[key]}"
            return "ERROR invalid key"

    def remove(self, key):
        with self.lock:
            if key in self.data:
                val = self.data.pop(key)
                return f"OK {val} deleted"
            return "ERROR invalid key"

    def list_all(self):
        with self.lock:
            if not self.data:
                return "DATA|"
            items = [f"{k}={v}" for k, v in self.data.items()]
            return f"DATA|{','.join(items)}"

    def count(self):
        with self.lock:
            return f"DATA {len(self.data)}"

    def clear(self):
        with self.lock:
            self.data.clear()
            return "all data deleted"

    def update(self, key, value):
        with self.lock:
            if key in self.data:
                self.data[key] = value
                return "Data updated"
            return "ERROR invalid key"

    def pop(self, key):
        with self.lock:
            if key in self.data:
                val = self.data.pop(key)
                return f"DATA {val}"
            return "ERROR invalid key"

state = State()

def process_command(command):
    parts = command.split()
    if not parts:
        return "ERROR empty command"

    cmd = parts[0].upper()
    
    if cmd == "ADD":
        if len(parts) < 3: return "ERROR ADD requires key and value"
        return state.add(parts[1], ' '.join(parts[2:]))
    
    elif cmd == "GET":
        if len(parts) != 2: return "ERROR GET requires key"
        return state.get(parts[1])
    
    elif cmd == "REMOVE":
        if len(parts) != 2: return "ERROR REMOVE requires key"
        return state.remove(parts[1])
    
    elif cmd == "LIST":
        return state.list_all()
    
    elif cmd == "COUNT":
        return state.count()
    
    elif cmd == "CLEAR":
        return state.clear()
    
    elif cmd == "UPDATE":
        if len(parts) < 3: return "ERROR UPDATE requires key and value"
        return state.update(parts[1], ' '.join(parts[2:]))
    
    elif cmd == "POP":
        if len(parts) != 2: return "ERROR POP requires key"
        return state.pop(parts[1])
    
    elif cmd == "QUIT":
        return "QUIT"
    
    return "ERROR unknown command"

def handle_client(client_socket):
    with client_socket:
        while True:
            try:
                data = client_socket.recv(BUFFER_SIZE)
                if not data:
                    break

                command = data.decode('utf-8').strip()
                response = process_command(command)
                
                if response == "QUIT":
                    client_socket.sendall("OK Goodbye".encode('utf-8'))
                    break
                
                client_socket.sendall(response.encode('utf-8'))

            except Exception as e:
                try:
                    client_socket.sendall(f"ERROR {str(e)}".encode('utf-8'))
                except:
                    pass
                break

def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen()
    print(f"[SERVER] Listening on {HOST}:{PORT}")

    try:
        while True:
            client_socket, addr = server_socket.accept()
            print(f"[SERVER] Connection from {addr}")
            threading.Thread(target=handle_client, args=(client_socket,)).start()
    except KeyboardInterrupt:
        print("[SERVER] Shutting down...")
    finally:
        server_socket.close()

if __name__ == "__main__":
    start_server()

tcp-server.py
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
        return f"{key} added"

    def get(self, key):
        with self.lock:
            return self.data.get(key, "Key not found")

    def remove(self, key):
        with self.lock:
            if key in self.data:
                del self.data[key]
                return f"{key} removed"
            return "Key not found"

state = State()

def process_command(command):
    parts = command.split()
    if len(parts) < 2:
        return "Invalid command format"

    cmd, key = parts[0], parts[1]
    
    if cmd == "add" and len(parts) > 2:
        return state.add(key, ' '.join(parts[2:]))
    elif cmd == "get" and len(parts) == 2:
        return state.get(key)
    elif cmd == "remove" and len(parts) == 2:
        return state.remove(key)
    
    return "Invalid command"

def handle_client(client_socket):
    with client_socket:
        while True:
            try:
                data = client_socket.recv(BUFFER_SIZE)
                if not data:
                    break

                command = data.decode('utf-8').strip()
                response = process_command(command)
                
                response_data = f"{len(response)} {response}".encode('utf-8')
                client_socket.sendall(response_data)

            except Exception as e:
                client_socket.sendall(f"Error: {str(e)}".encode('utf-8'))
                break

def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind((HOST, PORT))
        server_socket.listen()
        print(f"[SERVER] Listening on {HOST}:{PORT}")

        while True:
            client_socket, addr = server_socket.accept()
            print(f"[SERVER] Connection from {addr}")
            threading.Thread(target=handle_client, args=(client_socket,)).start()

if __name__ == "__main__":
    start_server()
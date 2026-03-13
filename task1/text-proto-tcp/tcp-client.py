import socket

HOST = "127.0.0.1"
PORT = 3333
BUFFER_SIZE = 1024

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect((HOST, PORT))
        except ConnectionRefusedError:
            print(f"[CLIENT] Nu ma pot conecta la {HOST}:{PORT}. Serverul ruleaza?")
            return

        print(f"[CLIENT] Conectat la {HOST}:{PORT}")
        print("Comenzi: ADD GET REMOVE LIST COUNT CLEAR UPDATE POP QUIT\n")

        while True:
            try:
                command = input("client> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n[CLIENT] Iesire.")
                break

            if not command:
                continue

            s.sendall(command.encode('utf-8'))

            response = s.recv(BUFFER_SIZE)
            if not response:
                print("[CLIENT] Conexiune inchisa de server.")
                break

            print(f"[SERVER] {response.decode('utf-8')}")

            if command.strip().upper() == "QUIT":
                break

if __name__ == "__main__":
    main()
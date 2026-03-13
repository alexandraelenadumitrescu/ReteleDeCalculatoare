import socket

HOST = "127.0.0.1"
PORT = 3333
BUFFER_SIZE = 1024

def main():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((HOST, PORT))
            print("Connected to server.")
            print("Commands: ADD, GET, REMOVE, LIST, COUNT, CLEAR, UPDATE, POP, QUIT")

            while True:
                command = input('client> ').strip()
                if not command:
                    continue

                s.sendall(command.encode('utf-8'))
                
                response_data = s.recv(BUFFER_SIZE)
                if not response_data:
                    print("Server closed connection.")
                    break
                
                response = response_data.decode('utf-8')
                print(f"Server response: {response}")

                if command.upper() == 'QUIT' or response == "OK Goodbye":
                    break

    except ConnectionRefusedError:
        print("Could not connect to server. Make sure it's running.")
    except Exception as e:
        print(f"Client error: {e}")

if __name__ == "__main__":
    main()

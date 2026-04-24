import socket
import sys

HOST = "127.0.0.1"
PORT = 9999
BUFFER_SIZE = 1024
TIMEOUT = 5

este_conectat = False
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(TIMEOUT)

def trimite_comanda(mesaj):
    try:
        sock.sendto(mesaj.encode('utf-8'), (HOST, PORT))
        raspuns, _ = sock.recvfrom(BUFFER_SIZE)
        return raspuns.decode('utf-8')
    except socket.timeout:
        return "ERROR timeout - serverul nu raspunde"
    except Exception as e:
        return f"ERROR {e}"

def main():
    global este_conectat

    print(f"[CLIENT] UDP gata. Server: {HOST}:{PORT}")
    print("Comenzi: CONNECT DISCONNECT PUBLISH DELETE LIST EXIT\n")

    while True:
        try:
            comanda = input("client> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[CLIENT] Iesire.")
            sock.close()
            sys.exit(0)

        if not comanda:
            continue

        cmd = comanda.split()[0].upper()

        if cmd == "EXIT":
            print("[CLIENT] Inchidere socket si iesire.")
            sock.close()
            sys.exit(0)

        elif cmd == "CONNECT":
            raspuns = trimite_comanda(comanda)
            print(f"[SERVER] {raspuns}")
            if raspuns.startswith("OK"):
                este_conectat = True

        elif cmd == "DISCONNECT":
            raspuns = trimite_comanda(comanda)
            print(f"[SERVER] {raspuns}")
            if raspuns.startswith("OK"):
                este_conectat = False

        elif cmd in ("PUBLISH", "DELETE", "LIST"):
            raspuns = trimite_comanda(comanda)
            print(f"[SERVER] {raspuns}")

        else:
            raspuns = trimite_comanda(comanda)
            print(f"[SERVER] {raspuns}")

if __name__ == "__main__":
    main()

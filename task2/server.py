import socket

HOST = "127.0.0.1"
PORT = 9999
BUFFER_SIZE = 1024

clienti = {}

def proceseaza_mesaj(data, addr):
    mesaj = data.decode('utf-8').strip()
    parts = mesaj.split()
    if not parts:
        return "ERROR comanda goala"

    cmd = parts[0].upper()

    if cmd == "CONNECT":
        if addr in clienti:
            return "ERROR client deja conectat"
        clienti[addr] = True
        print(f"[SERVER] (+) Client inregistrat: {addr} | Activi: {len(clienti)}")
        return "OK conectat"

    elif cmd == "DISCONNECT":
        if addr not in clienti:
            return "ERROR client neconectat"
        del clienti[addr]
        print(f"[SERVER] (-) Client deconectat: {addr} | Activi: {len(clienti)}")
        return "OK deconectat"

    elif cmd == "PUBLISH":
        if addr not in clienti:
            return "ERROR trebuie sa te conectezi mai intai"
        return f"OK publicat: {' '.join(parts[1:])}"

    elif cmd == "DELETE":
        if addr not in clienti:
            return "ERROR trebuie sa te conectezi mai intai"
        return f"OK sters: {' '.join(parts[1:])}"

    elif cmd == "LIST":
        if addr not in clienti:
            return "ERROR trebuie sa te conectezi mai intai"
        return f"OK lista: {list(clienti.keys())}"

    return f"ERROR comanda necunoscuta '{cmd}'"

def start_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, PORT))
    print(f"[SERVER] UDP pornit pe {HOST}:{PORT}")
    print("[SERVER] Comenzi acceptate: CONNECT DISCONNECT PUBLISH DELETE LIST\n")

    try:
        while True:
            try:
                data, addr = sock.recvfrom(BUFFER_SIZE)
                print(f"[SERVER] [{addr}] >> {data.decode('utf-8').strip()!r}")
                raspuns = proceseaza_mesaj(data, addr)
                sock.sendto(raspuns.encode('utf-8'), addr)
            except Exception as e:
                print(f"[SERVER] Eroare: {e}")
    except KeyboardInterrupt:
        print("[SERVER] Oprire...")
    finally:
        sock.close()

if __name__ == "__main__":
    start_server()

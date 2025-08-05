from enum import IntEnum
import socket
import json

class Header(IntEnum):
    StartWebTransport = 1
    StopWebTransport = 2
    Send = 3

if __name__ == '__main__':

    host = "127.0.0.1"
    port = 7000
    
    with socket.create_connection((host, port)) as sock:
        print("[PY] Connected to Unity server")
        
        while True:
            data = sock.recv(1024)
            print(f"[PY] Received response {data}")

            json_str = data.decode('utf-8')
            message = json.loads(json_str)

            if message["Header"] == Header.StartWebTransport:
                print("Starting web transport...")
            if message["Header"] == Header.StopWebTransport:
                print("Stoping web transport...")
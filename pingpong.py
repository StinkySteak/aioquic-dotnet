import socket
import json
import argparse
import asyncio
import threading

def ipc_receive_loop(sock):
    print("[PY] Running IPC Receive Loop")
    print("[PY] Sync Receiving...")
    sock.recv(1024)
    print("[PY] Received!")


if __name__ == '__main__':

    host = "127.0.0.1"
    port = 7000
    
    with socket.create_connection((host, port)) as sock:
        print("[PY] Connected to Unity server")
        threading.Thread(target=ipc_receive_loop, args=(sock,)).start()
        print("[PY] Main Thread")
        name = input("Enter a name: ")
from enum import IntEnum
import socket
import json
import argparse
import asyncio
import threading
import time

import logging
from collections import defaultdict
from typing import Dict, Optional

from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.h3.connection import H3_ALPN, H3Connection
from aioquic.h3.events import H3Event, HeadersReceived, WebTransportStreamDataReceived, DatagramReceived
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.connection import stream_is_unidirectional
from aioquic.quic.events import ProtocolNegotiated, StreamReset, QuicEvent
from _thread import start_new_thread
BIND_ADDRESS = '::1'
BIND_PORT = 4433

ipcSocket = None
Http3 = None

class NetickHandler:

    def __init__(self, session_id, http: H3Connection) -> None:
        self._session_id = session_id
        self._http = http
        self._counters = defaultdict(int)
        global Http3
        Http3 = http

    def h3_event_received(self, event: H3Event) -> None:
        if isinstance(event, DatagramReceived):
            payload = str(len(event.data)).encode('ascii')
            Log(f"Received message wtransport client: {payload} sessionId: {self._session_id}")
            self._http.send_datagram(self._session_id, payload)
            Log(f"Datagram replied!")

        if isinstance(event, WebTransportStreamDataReceived):
            self._counters[event.stream_id] += len(event.data)
            if event.stream_ended:
                if stream_is_unidirectional(event.stream_id):
                    response_id = self._http.create_webtransport_stream(
                        self._session_id, is_unidirectional=True)
                else:
                    response_id = event.stream_id
                payload = str(self._counters[event.stream_id]).encode('ascii')
                self._http._quic.send_stream_data(
                    response_id, payload, end_stream=True)
                self.stream_closed(event.stream_id)

    def stream_closed(self, stream_id: int) -> None:
        try:
            del self._counters[stream_id]
        except KeyError:
            pass

class WebTransportProtocol(QuicConnectionProtocol):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def echo():
        print("Echo")

    def quic_event_received(self, event: QuicEvent) -> None:
        if isinstance(event, ProtocolNegotiated):
            self._http = H3Connection(self._quic, enable_webtransport=True)
            self._handler: Optional[NetickHandler] = None
        elif isinstance(event, StreamReset) and self._handler is not None:
            # Streams in QUIC can be closed in two ways: normal (FIN) and
            # abnormal (resets).  FIN is handled by the handler; the code
            # below handles the resets.
            self._handler.stream_closed(event.stream_id)

        if self._http is not None:
            for h3_event in self._http.handle_event(event):
                self._h3_event_received(h3_event)

    def _h3_event_received(self, event: H3Event) -> None:
        if isinstance(event, HeadersReceived):
            headers = {}
            for header, value in event.headers:
                headers[header] = value
            if (headers.get(b":method") == b"CONNECT" and
                    headers.get(b":protocol") == b"webtransport"):
                self._handshake_webtransport(event.stream_id, headers)
            else:
                self._send_response(event.stream_id, 400, end_stream=True)

        if self._handler:
            self._handler.h3_event_received(event)

    def _handshake_webtransport(self,
                                stream_id: int,
                                request_headers: Dict[bytes, bytes]) -> None:
        authority = request_headers.get(b":authority")
        path = request_headers.get(b":path")
        if authority is None or path is None:
            # `:authority` and `:path` must be provided.
            self._send_response(stream_id, 400, end_stream=True)
            return
        if path == b"/":
            assert(self._handler is None)
            self._handler = NetickHandler(stream_id, self._http)
            self._send_response(stream_id, 200)
            print(f"a connection is established connectionid: {stream_id}")
            message = {
                "Header": 4,
                "ConnectionId": stream_id
            }
            json_str = json.dumps(message)
            data = json_str.encode('utf-8')

            ipcSocket.send(data)
            Log(f"Sending IPC of 'connectionEstablishment' to dotNET")
        else:
            self._send_response(stream_id, 404, end_stream=True)

    def _send_response(self,
                       stream_id: int,
                       status_code: int,
                       end_stream=False) -> None:
        headers = [(b":status", str(status_code).encode())]
        if status_code == 200:
            headers.append((b"sec-webtransport-http3-draft", b"draft02"))
        self._http.send_headers(
            stream_id=stream_id, headers=headers, end_stream=end_stream)
        

def startWebTransport():
    parser = argparse.ArgumentParser()
    parser.add_argument('certificate')
    parser.add_argument('key')
    args = parser.parse_args()

    configuration = QuicConfiguration(
        alpn_protocols=H3_ALPN,
        is_client=False,
        max_datagram_frame_size=65536,
    )
    configuration.load_cert_chain(args.certificate, args.key)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(
        serve(
            BIND_ADDRESS,
            BIND_PORT,
            configuration=configuration,
            create_protocol=WebTransportProtocol,
        ))
    try:
        logging.info(
            Log(f"Listening on https://{BIND_ADDRESS}:{BIND_PORT}"))
        loop.run_forever()
    except KeyboardInterrupt:
        pass

def Log(message):
    print(f"[Py]: {message}");

class Header(IntEnum):
    StartWebTransport = 1
    StopWebTransport = 2
    Send = 3
    OnConnectionEstablished = 4

def startWebTransportBeThread():
    Log("starting webtransport (2)")
    startWebTransport()

def ipc_receive_loop(sock):
    while True:
        Log(f"Socket receiving...")
        data = sock.recv(1024)
        Log(f"Received response {data}")
        json_str = data.decode('utf-8')
        message = json.loads(json_str)
        Log(f"message {message}")

        if message["Header"] == Header.StartWebTransport:
            Log("Starting web transport...")
            threading.Thread(target=startWebTransportBeThread).start()
        elif message["Header"] == Header.StopWebTransport:
            Log("Stopping web transport...")
        elif message["Header"] == Header.Send:
            connectionId = message["ConnectionId"]
            body = message["Body"]
            Log(f"Trying to forward dotNET message using {Http3} body: {body}")
            payload = str(len(body)).encode('ascii')
            Http3.send_datagram(connectionId, payload)
            Log(f"Datagram sent!")
        else:
            Log(f"Message header invalid!")


if __name__ == '__main__':

    host = "127.0.0.1"
    port = 7000
    
    with socket.create_connection((host, port)) as sock:
        ipcSocket = sock
        Log("[PY] Connected to Unity server")
        threading.Thread(target=ipc_receive_loop, args=(sock,)).start()

        while True:
            time.sleep(1)
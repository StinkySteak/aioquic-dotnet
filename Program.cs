using Newtonsoft.Json;
using System;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;

namespace WTransportLink
{
    internal class Program
    {
        public enum Header
        {
            StartWebTransport = 1,
            StopWebTransport = 2,
            Send = 3,
            OnConnectionEstablished = 4,
        }

        public class IPCWTransportMessage
        {
            public Header Header;
        }

        public class IPCWTransportMessageClientConnected
        {
            public Header Header;
            public int ConnectionId;
        }

        public class IPCWTransportMessageSend
        {
            public Header Header;
            public int ConnectionId;
            public byte[] Body;
        }

        private const string Python = "python";
        private const string Arguments = "index.py certificate.pem certificate.key";

        private Process _process;
        private IPCWTransport _ipcWTransport;

        static void Main(string[] args)
        {
            Program program = new Program();
            program.Run();
        }

        private void Run()
        {
            var psi = new ProcessStartInfo
            {
                FileName = Python,
                Arguments = Arguments,
                UseShellExecute = false,
            };

            Process.Start(psi);

            _ipcWTransport = new IPCWTransport();
            _ipcWTransport.Init();

            while (true)
            {
                _ipcWTransport.PollUpdate();

                Console.WriteLine("Menu:");
                Console.WriteLine("1. Start WTransport");

                AutoRun();
                return;

                string cmd = Console.ReadLine();
                int number = int.Parse(cmd);

                if (number == 1)
                    _ipcWTransport.StartWTransport();
                if (number == 2)
                    _ipcWTransport.StopWTransport();
            }
        }

        private void AutoRun()
        {
            _ipcWTransport.StartWTransport();
            Console.ReadLine();
        }

        public class IPCWTransport
        {
            private TcpListener _tcpListener;
            private TcpClient _wtransportIPCSocket;
            private int _listenPort = 7000;
            private bool _isIPCEstablished;

            private List<int> _connectionIds = new();
            private Thread _threadReceive;

            private static void Log(object message)
            {
                Console.WriteLine($"[.NET]: {message}");
            }

            public void Init()
            {
                _tcpListener = new TcpListener(IPAddress.Loopback, _listenPort);
                _tcpListener.Start();
                Log($"Tcp is listening at: {_listenPort}");
            }

            public void StartWTransport()
            {
                if (!_isIPCEstablished)
                {
                    Log($"No IPCWTranport client is connected");
                    return;
                }

                IPCWTransportMessage message = new();
                message.Header = Header.StartWebTransport;

                string json = JsonConvert.SerializeObject(message);
                byte[] bytes = Encoding.UTF8.GetBytes(json);

                _wtransportIPCSocket.Client.Send(bytes);

                _threadReceive = new Thread(LoopReceive);
                _threadReceive.Start();
            }

            public void StopWTransport()
            {
                if (!_isIPCEstablished)
                {
                    Log($"No IPCWTranport client is connected");
                    return;
                }

                IPCWTransportMessage message = new();
                message.Header = Header.StopWebTransport;

                string json = JsonConvert.SerializeObject(message);
                byte[] bytes = Encoding.UTF8.GetBytes(json);

                _wtransportIPCSocket.Client.Send(bytes);
            }

            private void LoopReceive()
            {
                while (true)
                {
                    if (!_isIPCEstablished)
                    {
                        continue;
                    }

                    byte[] buffer = new byte[20248];
                    int length = _wtransportIPCSocket.Client.Receive(buffer);

                    Log($"Message received (1), length: {length}");
                    string json = Encoding.UTF8.GetString(buffer, 0, length);

                    IPCWTransportMessageClientConnected message = JsonConvert.DeserializeObject<IPCWTransportMessageClientConnected>(json);

                    Log($"Message received (2) {json}");

                    _connectionIds.Add(message.ConnectionId);

                    AutoSendOnConnectEstablished(message.ConnectionId);
                }
            }

            private void AutoSendOnConnectEstablished(int connectionId)
            {
                Log($"Sending Message of empty bytes of array to: {connectionId}");

                byte[] random = new byte[32];

                for (int i = 0; i < 1; i++)
                {
                    SendToPeer(connectionId, random);
                }
            }

            private void SendToPeer(int connectionId, byte[] body)
            {
                IPCWTransportMessageSend message = new();
                message.Header = Header.Send;
                message.ConnectionId = connectionId;
                message.Body = body;

                string json = JsonConvert.SerializeObject(message);
                byte[] bytes = Encoding.UTF8.GetBytes(json);

                Log($"Sending netick packet...");
                _wtransportIPCSocket.Client.Send(bytes);
            }

            public void PollUpdate()
            {
                Log($"Poll Update...");
                _wtransportIPCSocket = _tcpListener.AcceptTcpClient();
                _isIPCEstablished = true;
            }
        }
    }
}

using Newtonsoft.Json;
using System.Diagnostics;
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
        }

        public class IPCWTransportMessage
        {
            public Header Header;
        }

        private const string Python = "python";
        private const string FileName = "index.py";

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
                Arguments = FileName,
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
                string cmd = Console.ReadLine();

                int number = int.Parse(cmd);

                if (number == 1)
                    _ipcWTransport.StartWTransport();
                if (number == 2)
                    _ipcWTransport.StopWTransport();
            }
        }

        public class IPCWTransport
        {
            private TcpListener _tcpListener;
            private TcpClient _wtransportIPCSocket;
            private int _listenPort = 7000;
            private bool _isClientConnected;

            public void Init()
            {
                _tcpListener = new TcpListener(IPAddress.Loopback, _listenPort);
                _tcpListener.Start();
                Console.WriteLine($"Tcp is listening at: {_listenPort}");
            }

            public void StartWTransport()
            {
                if (!_isClientConnected)
                {
                    Console.WriteLine($"No IPCWTranport client is connected");
                    return;
                }

                IPCWTransportMessage message = new();
                message.Header = Header.StartWebTransport;

                string json = JsonConvert.SerializeObject(message);
                byte[] bytes = Encoding.UTF8.GetBytes(json);

                _wtransportIPCSocket.Client.Send(bytes);
            }

            public void StopWTransport()
            {
                if (!_isClientConnected)
                {
                    Console.WriteLine($"No IPCWTranport client is connected");
                    return;
                }

                IPCWTransportMessage message = new();
                message.Header = Header.StopWebTransport;

                string json = JsonConvert.SerializeObject(message);
                byte[] bytes = Encoding.UTF8.GetBytes(json);

                _wtransportIPCSocket.Client.Send(bytes);
            }

            public void PollUpdate()
            {
                Console.WriteLine($"Poll Update...");
                _wtransportIPCSocket = _tcpListener.AcceptTcpClient();
                _isClientConnected = true;
            }
        }
    }
}

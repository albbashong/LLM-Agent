import threading
import socket
import select

class LLMSocketServer:
    def __init__(self, host='0.0.0.0', port=9002,):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.setblocking(False)  # 논블로킹 설정
        self.agent = {}  # fd: socket
        self.id_map = {}  # fd: client_id
        self.msg_buffer = {}  # fd: buffer
        self.web_server = None 
    def send_code(self, agent_fd: int, code: str):
                sock = self.agent.get(agent_fd)
                if sock:
                    try:
                        sock.sendall(code.encode())
                    except Exception as e:
                        print(f"[{agent_fd}] send failed: {e}")

    def start(self):
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(100)
        print(f"[Server] Listening on {self.host}:{self.port}")

        epoll = select.epoll()
        epoll.register(self.server_socket.fileno(), select.EPOLLIN)

        try:
            while True:
                events = epoll.poll(1)
                for fileno, event in events:
                    if fileno == self.server_socket.fileno():
                        client_sock, addr = self.server_socket.accept()
                        client_sock.setblocking(False)
                        epoll.register(client_sock.fileno(), select.EPOLLIN)
                        self.agent[client_sock.fileno()] = client_sock
                        client_id = f"user_{len(self.id_map)}"
                        self.id_map[client_sock.fileno()] = client_id
                        self.msg_buffer[client_sock.fileno()] = b""
                        print(f"[Server] Connected: {addr} as {client_id}")

                    elif event & select.EPOLLIN:
                        sock = self.agent[fileno]
                        try:
                            data = sock.recv(4096)
                            if data:
                                self.msg_buffer[fileno] += data
                                decoded = data.decode(errors="ignore")
                                client_id = self.id_map.get(fileno, "unknown")
                                print(f"[{client_id}] {decoded.strip()}")
                                if self.web_server:
                                    self.web_server.latest_agent_message = decoded.strip()
                            else:
                                self._close_client(epoll, fileno)
                        except ConnectionResetError:
                            self._close_client(epoll, fileno)

                    elif event & (select.EPOLLHUP | select.EPOLLERR):
                        self._close_client(epoll, fileno)

        finally:
            epoll.unregister(self.server_socket.fileno())
            epoll.close()
            self.server_socket.close()

    def _close_client(self, epoll, fileno):
        epoll.unregister(fileno)
        sock = self.agent.pop(fileno, None)
        client_id = self.id_map.pop(fileno, "unknown")
        self.msg_buffer.pop(fileno, None)
        if sock:
            sock.close()
            print(f"[Server] Disconnected: {client_id}")

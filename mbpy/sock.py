import asyncio
import socket
import sys
import time
from asyncio import AbstractEventLoopPolicy

import pytest
import contextlib
_SIZE = 1024 * 1024


def udp_sendto_dns(policy: AbstractEventLoopPolicy):
    loop = policy.get_event_loop()
    coro = loop.create_datagram_endpoint(
        asyncio.DatagramProtocol, local_addr=("0.0.0.0", 0), family=socket.AF_INET
    )

    s_transport, server = loop.run_until_complete(coro)


    s_transport.close()
    loop.run_until_complete(asyncio.sleep(0.01))

class SocketServer:
    def tcp_server(self, gen):
        sock = socket.socket()
        with sock:
            sock.setblocking(False)
            sock.bind(('127.0.0.1', 0))
            addr = sock.getsockname()
            sock.listen(1)
            gen(sock)
            yield addr
            
    loop = asyncio.get_event_loop()
    def socket_recv_into_and_close(self):
        def srv_gen(sock):
            time.sleep(1.2)
            sock.send(b"helo")

        async def kill(sock):
            await asyncio.sleep(0.2)
            sock.close()

        async def client(sock, addr):
            await self.loop.sock_connect(sock, addr)

            data = bytearray(10)
            with memoryview(data) as buf:
                f = asyncio.ensure_future(self.loop.sock_recv_into(sock, buf), loop=self.loop)
                self.loop.create_task(kill(sock))
                rcvd = await f
                data = data[:rcvd]
            return bytes(data)

        with self.tcp_server(srv_gen) as srv:
            sock = socket.socket()
            with sock:
                sock.setblocking(False)
                c = client(sock, srv.addr)
                w = asyncio.wait_for(c, timeout=5.0)
                r = self.loop.run_until_complete(w)
                assert r == b"helo"
    async def recv_all(self, sock, nbytes):
        buf = b''
        while len(buf) < nbytes:
            buf += await self.loop.sock_recv(sock, nbytes - len(buf))
        return buf

    def test_socket_accept_recv_send(self):
        async def server():
            sock = socket.socket()
            sock.setblocking(False)

            with sock:
                sock.bind(('127.0.0.1', 0))
                sock.listen()

                fut = self.loop.run_in_executor(None, client,
                                                sock.getsockname())

                client_sock, _ = await self.loop.sock_accept(sock)

                with client_sock:
                    data = await self.recv_all(client_sock, _SIZE)
                    self.assertEqual(data, b'a' * _SIZE)

                await fut

        def client(addr):
            sock = socket.socket()
            with sock:
                sock.connect(addr)
                sock.sendall(b'a' * _SIZE)

        self.loop.run_until_complete(server())

    def test_socket_failed_connect(self):
        sock = socket.socket()
        with sock:
            sock.bind(('127.0.0.1', 0))
            addr = sock.getsockname()

        async def run():
            sock = socket.socket()
            with sock:
                sock.setblocking(False)
                with self.assertRaises(ConnectionRefusedError):
                    await self.loop.sock_connect(sock, addr)

        self.loop.run_until_complete(run())


    def test_socket_ipv6_addr(self):
        server_sock = socket.socket(socket.AF_INET6)
        with server_sock:
            server_sock.bind(('::1', 0))

            addr = server_sock.getsockname()  # tuple of 4 elements for IPv6

            async def run():
                sock = socket.socket(socket.AF_INET6)
                with sock:
                    sock.setblocking(False)
                    # Check that sock_connect accepts 4-element address tuple
                    # for IPv6 sockets.
                    f = self.loop.sock_connect(sock, addr)
                    with contextlib.suppress(TimeoutError, ConnectionRefusedError):
                        await asyncio.wait_for(f, timeout=0.1)
                self.loop.run_until_complete(run())


        srv_sock_conn = None

        async def server():
            nonlocal srv_sock_conn
            sock_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock_server.setblocking(False)
            with sock_server:
                sock_server.bind(('127.0.0.1', 0))
                sock_server.listen()
                fut = asyncio.ensure_future(
                    client(sock_server.getsockname()))
                srv_sock_conn, _ = await self.loop.sock_accept(sock_server)
                srv_sock_conn.setsockopt(
                    socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                with srv_sock_conn:
                    await fut

        async def client(addr):
            sock_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock_client.setblocking(False)
            with sock_client:
                await self.loop.sock_connect(sock_client, addr)
                _, pending_read_futs = await asyncio.wait(
                    [
                        asyncio.ensure_future(
                            self.loop.sock_recv(sock_client, 1)
                        )
                    ],
                    timeout=1,
                )

                async def send_server_data():
                    # Wait a little bit to let reader future cancel and
                    # schedule the removal of the reader callback.  Right after
                    # "rfut.cancel()" we will call "loop.sock_recv()", which
                    # will add a reader.  This will make a race between
                    # remove- and add-reader.
                    await asyncio.sleep(0.1)
                    await self.loop.sock_sendall(srv_sock_conn, b'1')
                self.loop.create_task(send_server_data())

                for rfut in pending_read_futs:
                    rfut.cancel()

                data = await self.loop.sock_recv(sock_client, 1)

                assert data == b'1'

        self.loop.run_until_complete(server())

    def test_sock_send_before_cancel(self):
        if self.is_asyncio_loop() and sys.version_info[:2] == (3, 8):
            # asyncio 3.8.x has a regression; fixed in 3.9.0
            # tracked in https://bugs.python.org/issue30064
            raise unittest.SkipTest()

        srv_sock_conn = None

        async def server():
            nonlocal srv_sock_conn
            sock_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock_server.setblocking(False)
            with sock_server:
                sock_server.bind(('127.0.0.1', 0))
                sock_server.listen()
                fut = asyncio.ensure_future(
                    client(sock_server.getsockname()))
                srv_sock_conn, _ = await self.loop.sock_accept(sock_server)
                with srv_sock_conn:
                    await fut

        async def client(addr):
            await asyncio.sleep(0.01)
            sock_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock_client.setblocking(False)
            with sock_client:
                await self.loop.sock_connect(sock_client, addr)
                _, pending_read_futs = await asyncio.wait(
                    [
                        asyncio.ensure_future(
                            self.loop.sock_recv(sock_client, 1)
                        )
                    ],
                    timeout=1,
                )

                # server can send the data in a random time, even before
                # the previous result future has cancelled.
                await self.loop.sock_sendall(srv_sock_conn, b'1')

                for rfut in pending_read_futs:
                    rfut.cancel()

                data = await self.loop.sock_recv(sock_client, 1)

                self.assertEqual(data, b'1')

        self.loop.run_until_complete(server())


  
        sock = socket.socket()
        epoll = select.epoll.fromfd(self.loop._get_backend_id())

        try:
            cb = lambda: None

            sock.bind(('127.0.0.1', 0))
            sock.listen(0)
            fd = sock.fileno()
            self.loop.add_reader(fd, cb)
            self.loop.run_until_complete(asyncio.sleep(0.01))
            self.loop.remove_reader(fd)
            with self.assertRaises(FileNotFoundError):
                epoll.modify(fd, 0)

        finally:
            sock.close()
            self.loop.close()
            epoll.close()

    def test_add_reader_or_writer_transport_fd(self):
   
        async def runner():
            tr, pr = await self.loop.create_connection(
                lambda: asyncio.Protocol(), sock=rsock)

            try:
                cb = lambda: None
                sock = tr.get_extra_info('socket')

                with assert_raises():
                    self.loop.add_reader(sock, cb)
                with assert_raises():
                    self.loop.add_reader(sock.fileno(), cb)

                with assert_raises():
                    self.loop.remove_reader(sock)
                with assert_raises():
                    self.loop.remove_reader(sock.fileno())

                with assert_raises():
                    self.loop.add_writer(sock, cb)
                with assert_raises():
                    self.loop.add_writer(sock.fileno(), cb)

                with assert_raises():
                    self.loop.remove_writer(sock)
                with assert_raises():
                    self.loop.remove_writer(sock.fileno())

            finally:
                tr.close()

        rsock, wsock = socket.socketpair()
        try:
            self.loop.run_until_complete(runner())
        finally:
            rsock.close()
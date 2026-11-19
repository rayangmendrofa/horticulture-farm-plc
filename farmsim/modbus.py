"""Minimal Modbus TCP server and client (standard library only).

Function codes: 01 read coils, 02 read discrete inputs, 03 read holding
registers, 04 read input registers, 05 write single coil, 06 write single
register, 15 write multiple coils, 16 write multiple registers.
Interoperability with a third-party stack (pymodbus) is checked in
tests/test_modbus.py.
"""
from __future__ import annotations

import socket
import socketserver
import struct
import threading
import time

ILLEGAL_FUNCTION, ILLEGAL_ADDRESS, ILLEGAL_VALUE = 1, 2, 3


class ModbusError(Exception):
    def __init__(self, fc: int, code: int):
        super().__init__(f"Modbus exception {code} on function {fc}")
        self.fc, self.code = fc, code


class _Exc(Exception):
    def __init__(self, code):
        self.code = code


class ModbusImage:
    """The four Modbus tables, shared between the server and the application."""

    def __init__(self, coils=1024, discrete_inputs=1024, holding=2048, inputs=1024):
        self.coils = [False] * coils
        self.di = [False] * discrete_inputs
        self.hr = [0] * holding
        self.ir = [0] * inputs
        self.lock = threading.RLock()
        self.coil_write = 0.0          # time.monotonic() of the last coil write (I/O watchdog)


def _pack_bits(bits) -> bytes:
    out = bytearray((len(bits) + 7) // 8)
    for i, b in enumerate(bits):
        if b:
            out[i // 8] |= 1 << (i % 8)
    return bytes(out)


def _unpack_bits(data: bytes, count: int) -> list[bool]:
    return [bool(data[i // 8] >> (i % 8) & 1) for i in range(count)]


def process_pdu(image: ModbusImage, pdu: bytes) -> bytes:
    """Execute one request PDU against ``image`` and return the response PDU."""
    fc = pdu[0] if pdu else 0
    try:
        if fc in (1, 2, 3, 4):
            if len(pdu) != 5:
                raise _Exc(ILLEGAL_VALUE)
            addr, count = struct.unpack(">HH", pdu[1:5])
            limit = 2000 if fc in (1, 2) else 125
            if not 1 <= count <= limit:
                raise _Exc(ILLEGAL_VALUE)
            table = {1: image.coils, 2: image.di, 3: image.hr, 4: image.ir}[fc]
            if addr + count > len(table):
                raise _Exc(ILLEGAL_ADDRESS)
            with image.lock:
                values = table[addr:addr + count]
            if fc in (1, 2):
                data = _pack_bits(values)
            else:
                data = struct.pack(f">{count}H", *values)
            return bytes([fc, len(data)]) + data
        if fc == 5:
            addr, val = struct.unpack(">HH", pdu[1:5])
            if val not in (0x0000, 0xFF00):
                raise _Exc(ILLEGAL_VALUE)
            if addr >= len(image.coils):
                raise _Exc(ILLEGAL_ADDRESS)
            with image.lock:
                image.coils[addr] = val == 0xFF00
                image.coil_write = time.monotonic()
            return pdu[:5]
        if fc == 6:
            addr, val = struct.unpack(">HH", pdu[1:5])
            if addr >= len(image.hr):
                raise _Exc(ILLEGAL_ADDRESS)
            with image.lock:
                image.hr[addr] = val
            return pdu[:5]
        if fc in (15, 16):
            addr, count, nbytes = struct.unpack(">HHB", pdu[1:6])
            data = pdu[6:6 + nbytes]
            if len(data) != nbytes:
                raise _Exc(ILLEGAL_VALUE)
            if fc == 15:
                if not 1 <= count <= 1968 or nbytes != (count + 7) // 8:
                    raise _Exc(ILLEGAL_VALUE)
                if addr + count > len(image.coils):
                    raise _Exc(ILLEGAL_ADDRESS)
                with image.lock:
                    image.coils[addr:addr + count] = _unpack_bits(data, count)
                    image.coil_write = time.monotonic()
            else:
                if not 1 <= count <= 123 or nbytes != 2 * count:
                    raise _Exc(ILLEGAL_VALUE)
                if addr + count > len(image.hr):
                    raise _Exc(ILLEGAL_ADDRESS)
                with image.lock:
                    image.hr[addr:addr + count] = list(struct.unpack(f">{count}H", data))
            return struct.pack(">BHH", fc, addr, count)
        raise _Exc(ILLEGAL_FUNCTION)
    except _Exc as e:
        return bytes([(fc | 0x80) & 0xFF, e.code])
    except struct.error:
        return bytes([(fc | 0x80) & 0xFF, ILLEGAL_VALUE])


def _recv_exact(sock: socket.socket, n: int) -> bytes | None:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


class _Handler(socketserver.BaseRequestHandler):
    def handle(self):
        sock = self.request
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        image = self.server.image
        with self.server.conn_lock:
            self.server.connections.add(sock)
        try:
            self._serve(sock, image)
        finally:
            with self.server.conn_lock:
                self.server.connections.discard(sock)

    def _serve(self, sock, image):
        while True:
            try:
                head = _recv_exact(sock, 7)
                if head is None:
                    return
                tid, pid, length, uid = struct.unpack(">HHHB", head)
                if pid != 0 or not 2 <= length <= 254:
                    return
                pdu = _recv_exact(sock, length - 1)
                if pdu is None:
                    return
                resp = process_pdu(image, pdu)
                sock.sendall(struct.pack(">HHHB", tid, 0, len(resp) + 1, uid) + resp)
            except OSError:
                return


class _TCPServer(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


class ModbusServer:
    """Threaded Modbus TCP server serving a ``ModbusImage`` (any unit id)."""

    def __init__(self, image: ModbusImage, host: str = "0.0.0.0", port: int = 502):
        self.image = image
        self._srv = _TCPServer((host, port), _Handler)
        self._srv.image = image
        self._srv.connections = set()
        self._srv.conn_lock = threading.Lock()
        self.port = self._srv.server_address[1]
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._srv.serve_forever, daemon=True,
                                        name=f"modbus-server:{self.port}")
        self._thread.start()
        return self

    def stop(self):
        if self._thread is not None:
            self._srv.shutdown()
        self._srv.server_close()
        with self._srv.conn_lock:      # drop live client connections too
            for s in list(self._srv.connections):
                try:
                    s.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                s.close()


class ModbusClient:
    """Blocking Modbus TCP client; reconnects automatically on the next request."""

    def __init__(self, host: str, port: int = 502, unit: int = 1, timeout: float = 1.0):
        self.host, self.port, self.unit, self.timeout = host, port, unit, timeout
        self._sock = None
        self._tid = 0
        self._lock = threading.Lock()

    def close(self):
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None

    def _request(self, pdu: bytes) -> bytes:
        with self._lock:
            try:
                if self._sock is None:
                    self._sock = socket.create_connection((self.host, self.port), self.timeout)
                    self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self._tid = (self._tid + 1) & 0xFFFF
                self._sock.sendall(struct.pack(">HHHB", self._tid, 0, len(pdu) + 1, self.unit) + pdu)
                head = _recv_exact(self._sock, 7)
                if head is None:
                    raise ConnectionError("connection closed by server")
                tid, _, length, _ = struct.unpack(">HHHB", head)
                resp = _recv_exact(self._sock, length - 1)
                if resp is None or tid != self._tid:
                    raise ConnectionError("bad response")
            except OSError as e:
                self.close()
                raise ConnectionError(f"Modbus {self.host}:{self.port}: {e}") from e
        if resp[0] & 0x80:
            raise ModbusError(resp[0] & 0x7F, resp[1])
        return resp

    def _read(self, fc, addr, count):
        return self._request(struct.pack(">BHH", fc, addr, count))

    def read_coils(self, addr: int, count: int) -> list[bool]:
        return _unpack_bits(self._read(1, addr, count)[2:], count)

    def read_discrete_inputs(self, addr: int, count: int) -> list[bool]:
        return _unpack_bits(self._read(2, addr, count)[2:], count)

    def read_holding_registers(self, addr: int, count: int) -> list[int]:
        return list(struct.unpack(f">{count}H", self._read(3, addr, count)[2:]))

    def read_input_registers(self, addr: int, count: int) -> list[int]:
        return list(struct.unpack(f">{count}H", self._read(4, addr, count)[2:]))

    def write_coil(self, addr: int, value: bool):
        self._request(struct.pack(">BHH", 5, addr, 0xFF00 if value else 0))

    def write_register(self, addr: int, value: int):
        self._request(struct.pack(">BHH", 6, addr, value & 0xFFFF))

    def write_coils(self, addr: int, values) -> None:
        data = _pack_bits(values)
        self._request(struct.pack(">BHHB", 15, addr, len(values), len(data)) + data)

    def write_registers(self, addr: int, values) -> None:
        values = [v & 0xFFFF for v in values]
        self._request(struct.pack(f">BHHB{len(values)}H", 16, addr, len(values), 2 * len(values), *values))

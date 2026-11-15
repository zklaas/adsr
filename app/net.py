"""LAN play over TCP: the host runs the engine, clients only send moves.

Messages are JSON objects, one per line.
  client -> host   {"t": "hello", "name": ...}      {"t": "act", "action": {...}}
  host -> client   {"t": "welcome", "seat": n}       {"t": "lobby", "seats": [...]}
                   {"t": "view", "view": {...}}      {"t": "error", "msg": ...}
                   {"t": "bye", "msg": ...}
Uses QtNetwork so sockets run on the Qt event loop - no threads.
"""
from __future__ import annotations

import json

from PyQt6 import QtCore, QtNetwork

DEFAULT_PORT = 47420
MAX_LINE = 1 << 20


def _encode(msg: dict) -> bytes:
    return (json.dumps(msg, separators=(",", ":")) + "\n").encode("utf-8")


class _Line(QtCore.QObject):
    """A socket that delivers whole JSON messages."""
    message = QtCore.pyqtSignal(dict)
    closed = QtCore.pyqtSignal()

    def __init__(self, sock: QtNetwork.QTcpSocket, parent=None):
        super().__init__(parent)
        self.sock = sock
        self.buf = b""
        sock.readyRead.connect(self._read)
        sock.disconnected.connect(self.closed)

    def _read(self):
        self.buf += bytes(self.sock.readAll())
        if len(self.buf) > MAX_LINE:
            self.sock.abort()
            return
        while b"\n" in self.buf:
            line, self.buf = self.buf.split(b"\n", 1)
            try:
                msg = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if isinstance(msg, dict):
                self.message.emit(msg)

    def send(self, msg: dict):
        if self.sock.state() == QtNetwork.QAbstractSocket.SocketState.ConnectedState:
            self.sock.write(_encode(msg))
            self.sock.flush()


VIRTUAL_IFACES = ("docker", "br-", "veth", "virbr", "lxc", "vmnet", "tun", "tap")


def local_addresses() -> list[str]:
    """IPv4 addresses other machines could reach (skips loopback and
    container/VM bridges such as docker0)."""
    Flag = QtNetwork.QNetworkInterface.InterfaceFlag
    out = []
    for iface in QtNetwork.QNetworkInterface.allInterfaces():
        flags = iface.flags()
        if (not flags & Flag.IsUp or flags & Flag.IsLoopBack
                or iface.name().startswith(VIRTUAL_IFACES)):
            continue
        for entry in iface.addressEntries():
            ip = entry.ip()
            if ip.protocol() == QtNetwork.QAbstractSocket.NetworkLayerProtocol.IPv4Protocol:
                out.append(ip.toString())
    return out or ["127.0.0.1"]


class NetHost(QtCore.QObject):
    joined = QtCore.pyqtSignal(int, str)      # seat, player's name
    left = QtCore.pyqtSignal(int)             # seat
    action = QtCore.pyqtSignal(int, dict)     # seat, action

    def __init__(self, remote_seats: list[int], parent=None):
        super().__init__(parent)
        self.server = QtNetwork.QTcpServer(self)
        self.server.newConnection.connect(self._accept)
        self.free = list(remote_seats)
        self.lines: dict[int, _Line] = {}      # seat -> connection
        self.names: dict[int, str] = {}
        self.started = False

    def listen(self, port: int) -> str | None:
        if not self.server.listen(QtNetwork.QHostAddress.SpecialAddress.AnyIPv4, port):
            return self.server.errorString()
        return None

    def full(self) -> bool:
        return not self.free

    def _accept(self):
        while self.server.hasPendingConnections():
            sock = self.server.nextPendingConnection()
            line = _Line(sock, self)
            line.message.connect(lambda m, ln=line: self._hello(ln, m))
            line.closed.connect(lambda ln=line: self._drop(ln))

    def _seat_of(self, line):
        return next((s for s, ln in self.lines.items() if ln is line), None)

    def _hello(self, line: _Line, msg: dict):
        seat = self._seat_of(line)
        if seat is not None:
            if msg.get("t") == "act" and isinstance(msg.get("action"), dict):
                self.action.emit(seat, msg["action"])
            return
        if msg.get("t") != "hello":
            return
        if self.started or not self.free:
            line.send({"t": "bye", "msg": "That game is full or has already started."})
            line.sock.disconnectFromHost()
            return
        seat = self.free.pop(0)
        name = str(msg.get("name") or f"Player {seat + 1}").strip()[:24] or f"Player {seat + 1}"
        self.lines[seat] = line
        self.names[seat] = name
        line.send({"t": "welcome", "seat": seat})
        self.joined.emit(seat, name)

    def _drop(self, line: _Line):
        seat = self._seat_of(line)
        if seat is None:
            return
        del self.lines[seat]
        self.names.pop(seat, None)
        if not self.started:
            self.free.append(seat)
            self.free.sort()
        self.left.emit(seat)

    def send(self, seat: int, msg: dict):
        if seat in self.lines:
            self.lines[seat].send(msg)

    def broadcast(self, msg: dict):
        for line in self.lines.values():
            line.send(msg)

    def close(self, msg="The host closed the game."):
        self.broadcast({"t": "bye", "msg": msg})
        for line in list(self.lines.values()):
            line.sock.disconnectFromHost()
        self.server.close()


class NetClient(QtCore.QObject):
    welcome = QtCore.pyqtSignal(int)
    lobby = QtCore.pyqtSignal(list)
    view = QtCore.pyqtSignal(dict)
    error = QtCore.pyqtSignal(str)
    closed = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sock = QtNetwork.QTcpSocket(self)
        self.line = _Line(self.sock, self)
        self.line.message.connect(self._msg)
        self.line.closed.connect(lambda: self.closed.emit(self._bye or "Lost the connection to the host."))
        self.sock.errorOccurred.connect(self._err)
        self.sock.connected.connect(self._connected)
        self._name = ""
        self._was_connected = False
        self._bye = ""
        self.seat = None

    def connect_to(self, host: str, port: int, name: str):
        self._name = name
        self.sock.connectToHost(host, port)

    def _connected(self):
        self._was_connected = True
        self.line.send({"t": "hello", "name": self._name})

    def _err(self, _code):
        if not self._was_connected:      # later drops arrive via `disconnected`
            self.closed.emit(f"Could not connect: {self.sock.errorString()}")

    def _msg(self, m: dict):
        t = m.get("t")
        if t == "welcome":
            self.seat = int(m.get("seat"))
            self.welcome.emit(self.seat)
        elif t == "lobby":
            self.lobby.emit(list(m.get("seats") or []))
        elif t == "view" and isinstance(m.get("view"), dict):
            self.view.emit(m["view"])
        elif t == "error":
            self.error.emit(str(m.get("msg", "")))
        elif t == "bye":
            self._bye = str(m.get("msg", ""))

    def send_action(self, action: dict):
        self.line.send({"t": "act", "action": action})

    def close(self):
        self.sock.disconnectFromHost()

"""Socket-free HTTP transport for restricted test environments, never served live."""
from io import BytesIO
from types import SimpleNamespace
from .server import Handler


class MemoryConnection:
    def __init__(self, raw):
        self.input = BytesIO(raw)
        self.output = bytearray()

    def makefile(self, *args):
        return self.input

    def sendall(self, raw):
        self.output.extend(raw)

    def settimeout(self, timeout):
        pass


def request(service, method, path, body=b"", headers=None):
    headers = {"Host": "127.0.0.1:8000", "Connection": "close", **(headers or {})}
    if body:
        headers["Content-Length"] = str(len(body))
    raw = f"{method} {path} HTTP/1.1\r\n".encode()
    raw += b"".join(f"{k}: {v}\r\n".encode() for k, v in headers.items()) + b"\r\n" + body
    connection = MemoryConnection(raw)
    Handler(connection, ("127.0.0.1", 1), SimpleNamespace(service=service))
    head, data = bytes(connection.output).split(b"\r\n\r\n", 1)
    lines = head.decode().split("\r\n")
    return int(lines[0].split()[1]), dict(line.split(": ", 1) for line in lines[1:]), data

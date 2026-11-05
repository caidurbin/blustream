# Read-only follow-up: does the first command after connect get answered twice?
import socket
import sys
import time

HOST = sys.argv[1]


def run(port, cmds):
    s = socket.create_connection((HOST, port), timeout=5)
    s.settimeout(0.1)

    def drain(idle):
        buf = b""
        last = time.time()
        while time.time() - last < idle:
            try:
                d = s.recv(65536)
            except socket.timeout:
                continue
            if not d:
                break
            buf += d
            last = time.time()
        return buf

    drain(3)
    for c in cmds:
        assert c in ("UPTIME", "TEMP", "STATUS")
        t = time.time()
        s.sendall((c + "\r\n").encode())
        b = drain(3)
        print(
            port,
            c,
            "bytes",
            len(b),
            "count[SUCCESS]",
            b.count(b"[SUCCESS]"),
            "countStatusHdr",
            b.count(b"DMP168 Status"),
            "dur",
            round(time.time() - t - 3, 2),
        )
    s.close()


run(8000, ["UPTIME", "UPTIME", "STATUS"])
run(8000, ["STATUS", "STATUS"])
run(23, ["TEMP", "STATUS", "STATUS"])

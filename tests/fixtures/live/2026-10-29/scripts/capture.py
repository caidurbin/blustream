"""Read-only raw-socket capture of a Blustream DMP168.

Sends ONLY the whitelisted query commands below. Records every received
chunk with a monotonic timestamp relative to the send, as JSON lines.
Does not answer telnet IAC negotiation (passive client).
"""

import base64
import json
import socket
import sys
import time

HOST = sys.argv[1]
OUT = sys.argv[2]
ALLOWED = {
    "STATUS",
    "UPTIME",
    "TEMP",
    "HELP",
    "PRESET 1 STATUS",
    "PRESET 9 STATUS",
    "FOO",
}
SEQ = [
    "STATUS",
    "UPTIME",
    "TEMP",
    "HELP",
    "PRESET 1 STATUS",
    "PRESET 9 STATUS",
    "FOO",
    "STATUS",
]

log = open(OUT, "w")
T0 = time.time()


def rec(**kw):
    kw["wall"] = round(time.time() - T0, 4)
    if "data" in kw:
        b = kw.pop("data")
        kw["b64"] = base64.b64encode(b).decode()
        kw["repr"] = repr(b)
    log.write(json.dumps(kw) + "\n")
    log.flush()


def drain(sock, label, idle=2.0, maxwait=15.0):
    start = time.time()
    last = start
    total = b""
    sock.settimeout(0.1)
    while True:
        now = time.time()
        if now - last > idle or now - start > maxwait:
            break
        try:
            d = sock.recv(65536)
        except socket.timeout:
            continue
        if not d:
            rec(event="eof", label=label, t=round(time.time() - start, 4))
            break
        last = time.time()
        rec(event="recv", label=label, t=round(last - start, 4), data=d)
        total += d
    return total


def connect(port, label):
    s = socket.create_connection((HOST, port), timeout=5)
    rec(event="connect", label=label, port=port)
    drain(s, f"{label}:banner", idle=3.0)
    return s


for port in (23, 8000):
    a = connect(port, f"p{port}:A")
    for cmd in SEQ:
        assert cmd in ALLOWED, cmd
        rec(event="send", label=f"p{port}:A", cmd=cmd)
        a.sendall((cmd + "\r\n").encode())
        drain(a, f"p{port}:A:{cmd}")
    # Second client while A open: what does A receive?
    b = connect(port, f"p{port}:B")
    drain(a, f"p{port}:A:after-B-connect", idle=2.0)
    b.close()
    rec(event="close", label=f"p{port}:B")
    drain(a, f"p{port}:A:after-B-close", idle=1.5)
    a.close()
    rec(event="close", label=f"p{port}:A")
log.close()

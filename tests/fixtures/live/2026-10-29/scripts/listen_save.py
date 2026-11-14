# Passive: connect to both ports, send NOTHING, save every chunk with timestamps (JSONL).
import base64
import json
import select
import socket
import sys
import time

HOST = sys.argv[1]
N = float(sys.argv[2])
OUT = open(sys.argv[3], "w")
socks = {p: socket.create_connection((HOST, p), timeout=5) for p in (23, 8000)}
t0 = time.time()
while time.time() - t0 < N:
    r, _, _ = select.select(list(socks.values()), [], [], 0.2)
    for p, s in socks.items():
        if s in r:
            d = s.recv(65536)
            OUT.write(
                json.dumps(
                    {
                        "port": p,
                        "t": round(time.time() - t0, 4),
                        "b64": base64.b64encode(d).decode(),
                    }
                )
                + "\n"
            )
for s in socks.values():
    s.close()

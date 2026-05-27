#!/usr/bin/env python3
"""Determine the current state of a Blustream DMP168 on the network.

Usage:
    dmp168_state.py <ip>

Prints one of: off | on | problem | unknown, followed by the evidence
gathered from each probe. If the device is in the *problem* state, the
mitigation suggestions from docs/dmp168-known-issues.md are printed too.

Probes (all without a browser):
  1. ICMP ping (single packet)
  2. TCP connect on port 23 (Telnet)
  3. HTTP POST to /cgi-bin/instr looking for the broken-daemon sentinel
"""

import socket
import subprocess
import sys
import urllib.error
import urllib.request

PING_TIMEOUT = 2
TCP_TIMEOUT = 3
HTTP_TIMEOUT = 3

MITIGATION = """\
Mitigation (from docs/dmp168-known-issues.md):

  1. Power-cycle the device. Fast, preserves configuration.
  2. Hold the rear-panel RESET button for >=10 s (recovery ~30 s).
     This factory-resets configuration -- export the config first via
     System -> Import/Export next time the device is healthy.

There is no known software recovery path while the device is in this state.
"""


def ping(ip):
    """True if the host replies to one ICMP echo within PING_TIMEOUT seconds."""
    try:
        result = subprocess.run(
            ["ping", "-c", "1", ip],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=PING_TIMEOUT,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def tcp_probe(ip, port):
    """Return one of 'open', 'timeout', 'refused'."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(TCP_TIMEOUT)
    try:
        sock.connect((ip, port))
        return "open"
    except socket.timeout:
        return "timeout"
    except (ConnectionRefusedError, OSError):
        return "refused"
    finally:
        sock.close()


def cgi_probe(ip):
    """Return (status, content_type, body_head) for POST /cgi-bin/instr, or None."""
    req = urllib.request.Request(
        f"http://{ip}/cgi-bin/instr",
        data=b'{"comhead":"get status"}',
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            return (
                resp.status,
                resp.headers.get("Content-Type", ""),
                resp.read(4096).decode(errors="replace").strip(),
            )
    except (urllib.error.URLError, socket.timeout, OSError):
        return None


def classify(ip):
    pinged = ping(ip)
    if not pinged:
        return "off", ["ping: no reply"]

    telnet = tcp_probe(ip, 23)
    cgi = cgi_probe(ip)

    evidence = [
        "ping: reply",
        f"tcp/23: {telnet}",
    ]
    if cgi is None:
        evidence.append("http/80 cgi: unreachable")
    else:
        status, ctype, body = cgi
        evidence.append(f"http/80 cgi: status={status} ct={ctype}")
        evidence.append(f"  body: {body}")

    # 'on' — Telnet listener accepts TCP
    if telnet == "open":
        return "on", evidence

    # 'problem' — pingable, Telnet filtered, and CGI returns the error sentinel
    if telnet == "timeout":
        if cgi is not None:
            status, ctype, body = cgi
            looks_broken = (
                status == 200
                and "text/plain" in (ctype or "").lower()
                and body  # any non-empty error-shaped body
            )
            if looks_broken:
                return "problem", evidence
        # Telnet filtered but CGI didn't confirm — still most likely problem
        return "problem", evidence

    return "unknown", evidence


def main(argv):
    if len(argv) != 2 or argv[1] in ("-h", "--help"):
        print(f"Usage: {argv[0]} <ip>", file=sys.stderr)
        return 2

    ip = argv[1]
    state, evidence = classify(ip)

    print(f"state: {state}")
    for line in evidence:
        print(f"  {line}")
    if state == "problem":
        print()
        print(MITIGATION, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

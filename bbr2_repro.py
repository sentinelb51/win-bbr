"""
Script to reproduce the BBR2 loopback FIN-withholding bug on Windows.

    How it (does not) work:
    - Server sends N bytes over 127.0.0.1; then close() (FIN)
    - Client reads body, times how long the FIN takes to arrive
    - Body arrives instantly, but FIN is stalled on <~32 KB payloads

   Note:
   - Large payloads (e.g: 64 KB) close cleanly
"""

import re
import socket
import subprocess
import threading
import time

HOST: str = "127.0.0.1"
STALLED_THRESHOLD_MS: int = 500
FIN_TIMEOUT_SECONDS: int = 2

SMALL_PORT: int = 13000
SMALL_BYTES: int = 8_000  # trigger: cold, sub-32KB

LARGE_PORT: int = 13001
LARGE_BYTES: int = 65_000  # control: should always close fast


def _netsh_field(args: tuple[str, ...], field: str) -> str:
    """Run a netsh command and pull a single 'field : value' line out of its output."""
    output = subprocess.run(["netsh", *args], capture_output=True, text=True).stdout
    match = re.search(rf"{field}\s*:\s*(\S+)", output)
    return match.group(1) if match else "unknown"


def congestion_provider() -> str:
    return _netsh_field(("int", "tcp", "show", "supplemental"), "Congestion Control Provider")


def autotuning_level() -> str:
    return _netsh_field(("int", "tcp", "show", "global"), "Receive Window Auto-Tuning Level")


def loopback_large_mtu() -> str:
    return _netsh_field(("int", "ipv4", "show", "global"), "Loopback Large Mtu")




STARTUP_MESSAGE: str = f"""### Loopback stall test ###

Current environment:
 Congestion provider > {congestion_provider()}
 Auto-Tuning level   > {autotuning_level()}
 Loopback large MTU  > {loopback_large_mtu()}

Useful commands (admin):
 netsh int tcp set supplemental template=internet congestionprovider=  // bbr, cubic, ctcp, ...
 netsh int ipv4 set gl loopbacklargemtu=                               // enable, disable
"""


def fin_latency(port, nbytes):
    """Return (body_ms, fin_ms): time to receive all bytes, and extra time to FIN."""

    def server():
        listener = socket.socket()
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((HOST, port))
        listener.listen(1)

        s, _ = listener.accept()
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        s.sendall(b"X" * nbytes)
        s.close()  # graceful close -> FIN
        listener.close()

    server_thread = threading.Thread(target=server, daemon=True)
    server_thread.start()
    time.sleep(0.12)

    c = socket.socket()
    c.settimeout(FIN_TIMEOUT_SECONDS)
    c.connect((HOST, port))

    start = time.perf_counter()
    received = 0
    body_ms = None

    while True:
        try:
            data = c.recv(65536)
        except socket.timeout:
            c.close()
            server_thread.join(timeout=1)
            return body_ms, None  # FIN never came

        if not data:  # empty recv == FIN seen
            break

        received += len(data)
        if received >= nbytes and body_ms is None:
            body_ms = (time.perf_counter() - start) * 1000

    fin_ms = (time.perf_counter() - start) * 1000
    c.close()
    server_thread.join(timeout=1)
    return body_ms, fin_ms


def run(label, port, nbytes):
    body_ms, fin_ms = fin_latency(port, nbytes)

    if fin_ms is None:
        print(f" TIMEOUT > [{label:5s}] {nbytes:6d} bytes; body={body_ms:7.1f}ms  FIN=      ...")
        return False

    stalled = fin_ms > STALLED_THRESHOLD_MS
    print(
        f" {'STALLED' if stalled else 'OK     '} > [{label:5s}] {nbytes:6d} bytes; body={body_ms:7.1f}ms  FIN={fin_ms:7.1f}ms")
    return not stalled


if __name__ == "__main__":
    print(STARTUP_MESSAGE)
    print("Running 2 tests:")
    large_ok = run("Large", LARGE_PORT, LARGE_BYTES)
    small_ok = run("Small", SMALL_PORT, SMALL_BYTES)


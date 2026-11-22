"""Count wire UDP payload without retaining packet captures."""

import re
import select
import signal
import subprocess
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

UDP = re.compile(r"^IP (\S+) > (\S+): UDP, length (\d+)$")


@contextmanager
def capture_links(port):
    with TemporaryDirectory(prefix="moqt-wire-") as directory:
        path = Path(directory) / "trial.pcap"
        capture = subprocess.Popen(
            ["tcpdump", "-Z", "root", "-ni", "lo", "--immediate-mode", "-s", "96", "-w", str(path),
             f"ip and udp port {port}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
        )
        links = {}
        try:
            readable, _, _ = select.select([capture.stderr], [], [], 5)
            if not readable:
                raise TimeoutError("Packet capture did not become ready")
            ready = capture.stderr.readline()
            if "listening on lo" not in ready:
                raise RuntimeError(f"Capture could not start: {ready.strip()}")
            yield links
        finally:
            if capture.poll() is None:
                capture.send_signal(signal.SIGINT)
            try:
                _, stderr = capture.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                capture.kill()
                capture.communicate()
                raise
        if capture.returncode or not re.search(r"^0 packets dropped by kernel$", stderr, re.M):
            raise RuntimeError(f"Capture failed or dropped packets: {stderr.strip()}")
        output = subprocess.check_output(["tcpdump", "-Z", "root", "-nn", "-q", "-t", "-r", str(path)],
                                         stderr=subprocess.DEVNULL, text=True)
        for line in output.splitlines():
            match = UDP.search(line)
            if not match:
                raise RuntimeError(f"Unexpected decoded packet: {line}")
            source, target = (int(addr.rsplit(".", 1)[1]) for addr in match.groups()[:2])
            from_server = source == port
            peer = target if from_server else source
            counts = links.setdefault(peer, [0, 0, 0, 0])
            index = 2 if from_server else 0
            counts[index] += 1
            counts[index + 1] += int(match[3])


@contextmanager
def capture_udp(port):
    totals = [0, 0, 0, 0]
    with capture_links(port) as links:
        yield totals
    for counts in links.values():
        for index, value in enumerate(counts):
            totals[index] += value

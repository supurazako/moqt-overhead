"""Pilot: measure idle aiomoqt and aiopquic listener processes on Linux."""

import argparse
import asyncio
import importlib.util
import csv
import logging
import os
import random
import socket
import subprocess
import sys
import tempfile
from contextlib import AsyncExitStack, nullcontext
from pathlib import Path
from time import perf_counter_ns

from aiopquic.asyncio import connect, serve
from aiopquic.quic.configuration import QuicConfiguration

HOST = "127.0.0.1"
DRAFT = 22
ALPN = f"moqt-{DRAFT}"
SETTLE_SECONDS = 0.5
WINDOW_SECONDS = 1.0
SEED = 22
CPU_HZ = os.sysconf("SC_CLK_TCK")
ROOT = Path(__file__).resolve().parents[2]


def relay_command(name, port, work):
    source = ROOT / "experiments/fanout/measure.py"
    spec = importlib.util.spec_from_file_location("fanout_workload", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.relay_command(name, port, work)


async def quic_server(port, cert, key):
    config = QuicConfiguration(is_client=False, alpn_protocols=[ALPN],
                               congestion_control_algorithm="bbr",
                               max_datagram_frame_size=64 * 1024,
                               stream_ring_cap=1024 * 1024, max_connections=4096)
    config.load_cert_chain(cert, key)
    server = await serve(HOST, port, configuration=config)
    try:
        await asyncio.Future()
    finally:
        server.close()


async def wait_for_listener(process, port):
    async with asyncio.timeout(5):
        while process.poll() is None:
            for table in ("udp", "udp6"):
                with open(f"/proc/{process.pid}/net/{table}") as sockets:
                    for line in list(sockets)[1:]:
                        if line.split()[1].endswith(f":{port:04X}"):
                            return
            await asyncio.sleep(0.02)
        raise RuntimeError(f"Server exited with status {process.returncode}")


def memory_kib(pid):
    with open(f"/proc/{pid}/smaps_rollup") as smaps:
        metrics = {line.split()[0]: int(line.split()[1]) for line in smaps
                   if line.startswith(("Pss:", "Rss:"))}
    return metrics["Pss:"], metrics["Rss:"]


def cpu_ticks(pid):
    stat = Path(f"/proc/{pid}/stat").read_text()
    fields = stat.rsplit(")", 1)[1].split()
    return int(fields[11]) + int(fields[12])


def scheduled_runtime(pid):
    tasks = Path(f"/proc/{pid}/task")
    return {task.name: int((task / "schedstat").read_text().split()[0])
            for task in sorted(tasks.iterdir())}


async def measure(writer, kind, block, position, count, port, cert, key, wire, profile, fine_cpu, window):
    from aiomoqt.client import MOQTClient

    if profile != "aiomoqt" and kind == "moqt":
        command = relay_command(profile, port, Path(cert).parent)
    elif profile == "imquic":
        native = ROOT / ".scratch/native"
        command = ["env", f"LD_LIBRARY_PATH={native}", str(native / "imquic-echo-server"),
                   "-b", HOST, "-p", str(port), "-a", ALPN, "-q", "-d", "0", "-c", cert,
                   "-k", key]
    elif profile == "moqtail":
        command = [str(ROOT / ".scratch/native/moqtail-quic-baseline"), str(port), cert, key]
    elif kind == "quic":
        command = [sys.executable, __file__, "--quic-server", "--port", str(port),
                   "--cert", cert, "--key", key]
    else:
        command = [sys.executable, "-m", "aiomoqt.tools.moq_interop_relay",
                   "--bind", HOST, "--port", str(port), "--cert", cert, "--key", key,
                   "--quic", "--draft", str(DRAFT), "--startup-hold", "0",
                   "--log-level", "WARNING", "--cc-algo", "bbr",
                   "--stream-ring-cap", "1048576", "--max-connections", "4096"]
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.bind((HOST, port))
    process = subprocess.Popen(command, stdout=sys.stderr)
    try:
        await wait_for_listener(process, port)
        async with AsyncExitStack() as connections:
            if wire:
                from capture import capture_udp

            with capture_udp(port) if wire else nullcontext([]) as wire_counts:
                first_quic_us = first_setup_us = ""
                for index in range(count):
                    config = QuicConfiguration(is_client=True, alpn_protocols=[ALPN],
                                               cafile=cert, server_name="localhost",
                                               congestion_control_algorithm="bbr",
                                               max_datagram_frame_size=64 * 1024)
                    if kind == "moqt":
                        client = MOQTClient(HOST, port, use_quic=True,
                                            configuration=config, supported_drafts=DRAFT)
                        connection = client.connect()
                    else:
                        connection = connect(HOST, port, configuration=config)
                    async with asyncio.timeout(5):
                        start = perf_counter_ns()
                        session = await connections.enter_async_context(connection)
                        quic_us = (perf_counter_ns() - start) / 1_000
                        setup_us = ""
                        if kind == "moqt":
                            start = perf_counter_ns()
                            await session.client_session_init()
                            setup_us = (perf_counter_ns() - start) / 1_000
                            if session.negotiated_draft != DRAFT:
                                raise RuntimeError("Unexpected MoQT draft")
                    if index == 0:
                        first_quic_us, first_setup_us = quic_us, setup_us
                await asyncio.sleep(SETTLE_SECONDS)
                start = perf_counter_ns()
                if fine_cpu:
                    first_runtime = scheduled_runtime(process.pid)
                ticks = cpu_ticks(process.pid)
                await asyncio.sleep(window)
                elapsed_s = (perf_counter_ns() - start) / 1e9
                delta_ticks = cpu_ticks(process.pid) - ticks
                cpu_ns = []
                if fine_cpu:
                    end_runtime = scheduled_runtime(process.pid)
                    cpu_ns = [sum(end_runtime.values()) - sum(first_runtime.values())
                              if end_runtime.keys() == first_runtime.keys() else ""]
                pss, rss = memory_kib(process.pid)
            writer.writerow([block, position, kind, count, pss, rss, round(elapsed_s, 6),
                             delta_ticks, CPU_HZ, first_quic_us, first_setup_us, *cpu_ns, *wire_counts])
            sys.stdout.flush()
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


async def run(args):
    logging.getLogger().setLevel(logging.WARNING)
    with tempfile.TemporaryDirectory(prefix="moq-overhead-") as directory:
        cert = str(Path(directory) / "cert.pem")
        key = str(Path(directory) / "key.pem")
        subprocess.run(
            ["openssl", "req", "-x509", "-newkey", "ec",
             "-pkeyopt", "ec_paramgen_curve:P-256", "-noenc", "-days", "1",
             "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost",
             "-keyout", key, "-out", cert],
            check=True, stdout=sys.stderr,
        )
        writer = csv.writer(sys.stdout, lineterminator="\n")
        columns = ["block", "position", "server", "connections", "pss_kib", "rss_kib",
                   "idle_window_s", "cpu_ticks", "cpu_hz", "first_quic_ready_us",
                   "first_moqt_setup_us"]
        if args.fine_cpu:
            columns.append("scheduled_cpu_ns")
        if args.capture:
            columns.extend(("client_datagrams", "client_udp_bytes", "server_datagrams",
                            "server_udp_bytes"))
        writer.writerow(columns)
        rng = random.Random(SEED)
        cases = []
        for count in args.connections:
            orders = [("quic", "moqt"), ("moqt", "quic")] * (args.blocks // 2)
            rng.shuffle(orders)
            cases.extend((block, count, order) for block, order in enumerate(orders, 1))
        rng.shuffle(cases)
        for block, count, order in cases:
            for position, kind in enumerate(order, 1):
                await measure(writer, kind, block, position, count, args.port, cert, key, args.capture, args.profile, args.fine_cpu, args.window)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=45443)
    parser.add_argument("--fine-cpu", action="store_true", help="Record per-thread scheduled runtime")
    parser.add_argument("--profile", choices=("aiomoqt", "imquic", "moqtail"), default="aiomoqt")
    parser.add_argument("--capture", action="store_true", help="Capture loopback UDP in an isolated namespace")
    parser.add_argument("--connections", nargs="+", type=int, choices=range(5), default=list(range(5)))
    parser.add_argument("--window", type=float, default=WINDOW_SECONDS)
    parser.add_argument("--blocks", type=int, default=6)
    parser.add_argument("--quic-server", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--cert", help=argparse.SUPPRESS)
    parser.add_argument("--key", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.quic_server:
        asyncio.run(quic_server(args.port, args.cert, args.key))
    else:
        if not 1 <= args.port <= 65535 or args.blocks < 2 or args.blocks % 2:
            parser.error("Use a valid UDP port and a positive, even block count")
        if not 0 < args.window <= 20 or len(set(args.connections)) != len(args.connections):
            parser.error("Use a window of up to 20 seconds and unique connection counts")
        asyncio.run(run(args))

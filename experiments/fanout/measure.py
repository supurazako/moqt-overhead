"""Draft-22 fanout pilot with separate endpoint processes and role metrics."""

import argparse
import asyncio
import itertools
import json
import logging
import os
import random
import socket
import subprocess
import sys
import tempfile
from contextlib import AsyncExitStack, ExitStack
from pathlib import Path
from time import monotonic_ns

from aiomoqt.client import MOQTClient
from aiomoqt.tools.moq_interop_client import (
    _DataPublisher, _DataSubscriber, _is_normal,
)
from aiomoqt.tools.moqtest_origin import parse_namespace
from aiomoqt.track import SubscribedTrack
from aiomoqt.types import GroupOrder, MOQTMessageType

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments/idle"))
from capture import capture_links

PORT = 45447
NAMESPACE = ("moq-test", "fanout-pilot")
TRACK = "track"
GROUPS = 4
OBJECTS = 30
PAYLOAD = 8192
INTERVAL_MS = 20
CASE = ("moq-test-00", "0", "0", "0", str(GROUPS - 1), str(OBJECTS - 1),
        str(OBJECTS), str(PAYLOAD), str(PAYLOAD), str(INTERVAL_MS), "1", "1", "0", "-1", "-1", "0")
RELAY_NAMES = ("aiomoqt", "imquic", "moqtail")
WORKLOAD = parse_namespace(CASE)
if (WORKLOAD.last_group, WORKLOAD.last_object, WORKLOAD.freq_ms,
        WORKLOAD.size0, WORKLOAD.size_gt0) != (GROUPS - 1, OBJECTS - 1, INTERVAL_MS, PAYLOAD, PAYLOAD):
    raise ValueError("Test namespace does not match the planned workload")


def emit(**row):
    print(json.dumps(row), flush=True)


def endpoint_event(name, **fields):
    emit(event=name, ns=monotonic_ns(), **fields)


async def wait_for_command():
    if await asyncio.to_thread(sys.stdin.readline) != "go\n":
        raise RuntimeError("Controller closed the endpoint command stream")


class Subscriber(_DataSubscriber):
    def __init__(self):
        super().__init__()
        self.seen = set()
        self.errors = 0

    def on_object(self, msg, size, ts, group_id, subgroup_id):
        if not _is_normal(getattr(msg, "status", None)):
            return
        if not self.seen:
            endpoint_event("first_object")
        location = group_id, msg.object_id
        if (location in self.seen or group_id not in range(GROUPS)
                or msg.object_id not in range(OBJECTS) or subgroup_id != 0
                or msg.payload != b"t" * PAYLOAD):
            self.errors += 1
        self.seen.add(location)
        if os.getenv("MOQ_END_TRACE") and location == (GROUPS - 1, OBJECTS - 1):
            endpoint_event("final_object_received")

    def on_done(self, msg):
        if os.getenv("MOQ_END_TRACE"):
            endpoint_event("publish_done_received", stream_count=msg.stream_count)
        super().on_done(msg)


async def endpoint(role, port, cert):
    logging.disable(logging.INFO)
    client = MOQTClient("127.0.0.1", port, use_quic=True, ca_file=cert, supported_drafts=22)
    if role == "publisher":
        publisher = _DataPublisher(tuple(part.encode() for part in NAMESPACE), TRACK.encode())
        client.register_handler(MOQTMessageType.SUBSCRIBE, publisher.on_subscribe)
    endpoint_event("ready")
    await wait_for_command()
    endpoint_event("connect_start")
    async with client.connect() as session:
        endpoint_event("quic_connected")
        await session.client_session_init()
        if session.negotiated_draft != 22:
            raise RuntimeError("Unexpected draft")
        endpoint_event("setup_done")
        if role == "publisher":
            await session.publish_namespace(namespace="/".join(NAMESPACE), wait_response=True)
            endpoint_event("published")
            await wait_for_command()
            await asyncio.wait_for(publisher.subscribed.wait(), 5)
            endpoint_event("send_start")
            if os.getenv("MOQ_END_TRACE"):
                send_done = session.subscribe_done
                pending = []

                def queue_done(**fields):
                    endpoint_event("data_and_fin_queued")
                    pending.append(fields)

                session.subscribe_done = queue_done
                try:
                    streams = await publisher.send(session)
                finally:
                    session.subscribe_done = send_done
                if pending:
                    delay = int(os.getenv("MOQ_END_DELAY_MS", "0"))
                    if delay:
                        await asyncio.sleep(delay / 1000)
                    send_done(**pending[0])
                    endpoint_event("publish_done_queued")
            else:
                streams = await publisher.send(session)
            endpoint_event("sent", streams=streams, done=publisher.done_sent)
        else:
            subscriber = Subscriber()
            track = SubscribedTrack(
                session, "/".join((*NAMESPACE, *CASE)), TRACK,
                on_object=subscriber.on_object, on_done=subscriber.on_done,
            )
            await track.subscribe(forward=None, group_order=GroupOrder.ASCENDING)
            session.register_stream_end_handler(track.track_alias, subscriber.on_stream_end)
            endpoint_event("subscribed")
            await subscriber.drain(asyncio.get_running_loop().time() + 7)
            endpoint_event("received", objects=len(subscriber.seen), errors=subscriber.errors,
                           missing=sorted(set(itertools.product(range(GROUPS), range(OBJECTS)))
                                          - subscriber.seen),
                           streams=subscriber.streams_ended, resets=subscriber.streams_reset,
                           done=subscriber.done is not None)
        await wait_for_command()


def relay_command(name, port, work):
    cert, key = str(work / "cert.pem"), str(work / "key.pem")
    native = ROOT / ".scratch/native"
    if name == "aiomoqt":
        return [sys.executable, "-m", "aiomoqt.tools.moq_interop_relay",
                "--bind", "127.0.0.1", "--port", str(port), "--quic", "--draft", "22",
                "--cert", cert, "--key", key, "--log-level", "WARNING"]
    if name == "imquic":
        return ["env", f"LD_LIBRARY_PATH={native}", str(native / "imquic-moq-relay"),
                "-b", "127.0.0.1", "-p", str(port), "-M", "22", "-q", "-d",
                "4" if os.getenv("MOQ_RELAY_TRACE") else "0",
                "-c", cert, "-k", key]
    if name == "moqtail":
        return ["env", "RUST_LOG=warn", str(native / "moqtail"), "--host", "127.0.0.1",
                "--port", str(port), "--cert-file", cert, "--key-file", key,
                "--log-folder", str(work)]
    raise ValueError(name)


def snapshot(pid):
    proc = Path(f"/proc/{pid}")
    values = {}
    for line in (proc / "smaps_rollup").read_text().splitlines():
        if line.startswith(("Pss:", "Rss:")):
            name, value, _ = line.split()
            values[name[:-1].lower() + "_kib"] = int(value)
    runtime = 0
    threads = []
    for task in sorted((proc / "task").iterdir()):
        runtime += int((task / "schedstat").read_text().split()[0])
        threads.append(task.name)
    return values, runtime, tuple(threads)


def udp_ports(pid):
    proc = Path(f"/proc/{pid}")
    inodes = set()
    for descriptor in (proc / "fd").iterdir():
        try:
            target = str(descriptor.readlink())
        except FileNotFoundError:
            continue
        if target.startswith("socket:["):
            inodes.add(target[8:-1])
    ports = set()
    for table in ("udp", "udp6"):
        for line in (proc / "net" / table).read_text().splitlines()[1:]:
            fields = line.split()
            if fields[9] in inodes:
                ports.add(int(fields[1].split(":")[1], 16))
    return ports


async def stop(child):
    if child.returncode is None:
        child.terminate()
        try:
            await asyncio.wait_for(child.wait(), 2)
        except TimeoutError:
            child.kill()
            await child.wait()


async def read_until(child, role, name, report):
    async with asyncio.timeout(10):
        while raw := await child.stdout.readline():
            row = json.loads(raw)
            report(role=role, **row)
            if row["event"] == name:
                return row
    raise RuntimeError(f"{role} exited before {name}")


async def command(child):
    child.stdin.write(b"go\n")
    await child.stdin.drain()


async def measure(name, count, block, position, port, work, wire, hops=None):
    def report(**row):
        emit(relay=name, subscribers=count, block=block, position=position,
             **({"hops": hops} if hops else {}), **row)

    async with AsyncExitStack() as stack:
        async def launch_relay(listen_port, extra=()):
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                probe.bind(("127.0.0.1", listen_port))
            child = await asyncio.create_subprocess_exec(
                *relay_command(name, listen_port, work), *extra, cwd=work, stdout=sys.stderr,
            )
            stack.push_async_callback(stop, child)
            async with asyncio.timeout(5):
                while True:
                    if child.returncode is not None:
                        raise RuntimeError(f"Relay exited: {child.returncode}")
                    sockets = Path("/proc/net/udp").read_text() + Path("/proc/net/udp6").read_text()
                    if f":{listen_port:04X} " in sockets:
                        return child
                    await asyncio.sleep(0.02)

        roles = {"relay": await launch_relay(port)}
        subscriber_port = port
        if hops == 2:
            subscriber_port = port + 1
            roles["relay-edge"] = await launch_relay(
                subscriber_port, ("--upstream", f"moqt://127.0.0.1:{port}"),
            )

        async def launch(role):
            child = await asyncio.create_subprocess_exec(
                sys.executable, __file__, "--role", role.split("-")[0], "--port",
                str(port if role == "publisher" else subscriber_port),
                "--cert", str(work / "cert.pem"),
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            )
            roles[role] = child
            stack.push_async_callback(stop, child)
            await read_until(child, role, "ready", report)

        def take_all():
            return {role: snapshot(child.pid) for role, child in roles.items()}

        def report_samples(phase, start, before):
            end = monotonic_ns()
            for role, (mem, cpu, tids) in take_all().items():
                _, prior, prior_tids = before[role]
                report(role=role, event="sample", phase=phase, window_ns=end - start,
                       cpu_ns=cpu - prior if tids == prior_tids else None, **mem)

        async def idle(phase):
            await asyncio.sleep(0.35)
            before = take_all()
            start = monotonic_ns()
            await asyncio.sleep(1)
            report_samples(phase, start, before)

        await launch("publisher")
        subscribers = [f"subscriber-{index + 1}" for index in range(count)]
        await asyncio.gather(*(launch(role) for role in subscribers))
        await idle("disconnected")
        with ExitStack() as captures:
            links = captures.enter_context(capture_links(port)) if wire else {}
            edge_links = captures.enter_context(capture_links(subscriber_port)) if wire and hops == 2 else links
            await command(roles["publisher"])
            await read_until(roles["publisher"], "publisher", "published", report)
            for role in subscribers:
                await command(roles[role])
            await asyncio.gather(*(read_until(roles[role], role, "subscribed", report)
                                   for role in subscribers))
            await idle("subscribed")
            before = take_all()
            start = monotonic_ns()
            await command(roles["publisher"])
            tasks = [read_until(roles["publisher"], "publisher", "sent", report)]
            tasks.extend(read_until(roles[role], role, "received", report) for role in subscribers)
            sent, *received = await asyncio.gather(*tasks)
            report_samples("transfer", start, before)
            passed = (sent["done"] and sent["streams"] == GROUPS
                      and all(row["objects"] == GROUPS * OBJECTS and row["errors"] == 0
                              and row["streams"] == GROUPS and row["resets"] == 0 and row["done"]
                              for row in received))
            if wire:
                await asyncio.sleep(0.1)
            client_ports = {role: udp_ports(child.pid) for role, child in roles.items()
                            if wire and role != "relay"}
        if wire:
            used_ports = set()
            for role, ports in client_ports.items():
                role_links = edge_links if role.startswith("subscriber") else links
                matched = (ports & role_links.keys()) - used_ports
                if len(matched) != 1:
                    raise RuntimeError(f"Cannot attribute UDP link for {role}")
                peer = matched.pop()
                used_ports.add(peer)
                tx_count, tx_bytes, rx_count, rx_bytes = role_links[peer]
                delivered = (GROUPS * OBJECTS if role in ("publisher", "relay-edge") else
                             received[subscribers.index(role)]["objects"])
                payload = tx_bytes if role == "publisher" else rx_bytes
                if payload < delivered * PAYLOAD:
                    raise RuntimeError(f"UDP capture smaller than Object payload for {role}")
                report(role=role, event="wire", tx_datagrams=tx_count, tx_udp_bytes=tx_bytes,
                       rx_datagrams=rx_count, rx_udp_bytes=rx_bytes)
            if used_ports != links.keys() | edge_links.keys():
                raise RuntimeError("Unattributed UDP links")
        report(event="trial_completed", passed=passed)
        for role, child in roles.items():
            if not role.startswith("relay"):
                await command(child)
        async with asyncio.timeout(5):
            await asyncio.gather(*(child.wait() for role, child in roles.items() if not role.startswith("relay")))
        if not passed:
            raise RuntimeError("Object delivery validation failed")


async def run(args):
    rng = random.Random(22)
    cases = []
    for count in args.subscribers:
        if args.topology:
            orders = [(1, 2), (2, 1)] * (args.topology_pairs // 2)
            rng.shuffle(orders)
            cases.extend((count, block, order) for block, order in enumerate(orders, 1))
            continue
        orders = list(itertools.permutations(args.relays)) if args.pilot else [tuple(args.relays)]
        rng.shuffle(orders)
        cases.extend((count, block, order) for block, order in enumerate(orders, 1))
    rng.shuffle(cases)
    with tempfile.TemporaryDirectory(prefix="moqt-fanout-") as directory:
        work = Path(directory)
        subprocess.run(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt",
                        "ec_paramgen_curve:P-256", "-noenc", "-days", "1", "-subj", "/CN=localhost",
                        "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1",
                        "-keyout", str(work / "key.pem"), "-out", str(work / "cert.pem")],
                       check=True, stdout=sys.stderr)
        failures = 0
        for count, block, order in cases:
            for position, arm in enumerate(order, 1):
                name, hops = ("aiomoqt", arm) if args.topology else (arm, None)
                try:
                    await measure(name, count, block, position, args.port, work, args.capture, hops)
                except Exception as error:
                    emit(relay=name, subscribers=count, block=block, position=position,
                         event="trial_failed", error=str(error), **({"hops": hops} if hops else {}))
                    failures += 1
        if failures:
            raise RuntimeError(f"{failures} trial(s) failed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", choices=("publisher", "subscriber"))
    parser.add_argument("--cert")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--subscribers", nargs="+", type=int, choices=range(1, 5), default=[1, 2, 3, 4])
    parser.add_argument("--relays", nargs="+", choices=RELAY_NAMES, default=list(RELAY_NAMES))
    parser.add_argument("--topology", action="store_true", help="Compare one and two aiomoqt relays")
    parser.add_argument("--topology-pairs", type=int, default=6)
    parser.add_argument("--capture", action="store_true")
    parser.add_argument("--pilot", action="store_true", help="Use all six balanced orders")
    args = parser.parse_args()
    if args.topology and (args.topology_pairs < 2 or args.topology_pairs % 2):
        parser.error("Topology requires a positive, even pair count")
    asyncio.run(endpoint(args.role, args.port, args.cert) if args.role else run(args))

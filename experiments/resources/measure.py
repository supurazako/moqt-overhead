"""Role-separated connection and sustained multi-track resource measurements."""
import argparse
import ctypes
import asyncio
import itertools
import json
import logging
import random
import socket
import subprocess
import sys
import tempfile
from contextlib import AsyncExitStack
from pathlib import Path
from time import monotonic_ns, clock_gettime_ns

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'experiments/fanout'))
from measure import command, emit, read_until, relay_command, stop, udp_ports
from capture import capture_links
from aiomoqt.client import MOQTClient
from aiomoqt.context import profile_for
from aiomoqt.messages.data import SubgroupHeader
from aiomoqt.track import SubscribedTrack
from aiomoqt.types import GroupOrder, MOQTMessageType, SubscribeDoneCode

RELAYS = ('aiomoqt', 'imquic', 'moqtail')
NAMESPACE = 'moq-test/resources'

# Linux process clocks retain CPU consumed by threads after those threads exit.
LIBC = ctypes.CDLL(None)
LIBC.clock_getcpuclockid.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
LIBC.clock_getcpuclockid.restype = ctypes.c_int


def snapshot(pid):
    memory = {}
    for line in Path(f'/proc/{pid}/smaps_rollup').read_text().splitlines():
        if line.startswith(('Pss:', 'Rss:')):
            name, value, _ = line.split()
            memory[name[:-1].lower() + '_kib'] = int(value)
    clock = ctypes.c_int()
    error = LIBC.clock_getcpuclockid(pid, ctypes.byref(clock))
    if error:
        raise OSError(error, 'Cannot obtain process CPU clock')
    return memory, clock_gettime_ns(clock.value), ('process-cpu-clock',)


async def endpoint(args):
    logging.disable(logging.INFO)
    requests = {}
    seen = set()
    errors = 0
    first = None
    client = MOQTClient('127.0.0.1', args.port, use_quic=True,
                        ca_file=args.cert, supported_drafts=22)

    async def accept(session, msg):
        name = bytes(msg.track_name)
        if name in requests:
            raise RuntimeError('Duplicate upstream subscription')
        ok = session.subscribe_ok(request_msg=msg)
        requests[name] = (msg.request_id, ok.track_alias)

    def receive(track_index, msg, size, timestamp, group_id, subgroup_id):
        nonlocal errors, first
        if not msg.payload:
            return
        if first is None:
            first = monotonic_ns()
        location = track_index, group_id, msg.object_id
        if (location in seen or msg.payload != b't' * args.payload
                or group_id != 0 or subgroup_id != 0
                or msg.object_id not in range(args.objects)):
            errors += 1
        seen.add(location)

    if args.role == 'publisher':
        client.register_handler(MOQTMessageType.SUBSCRIBE, accept)
    async with client.connect() as session:
        await session.client_session_init()
        if session.negotiated_draft != 22:
            raise RuntimeError('Unexpected draft')
        if args.role == 'publisher':
            await session.publish_namespace(namespace=NAMESPACE, wait_response=True)
        emit(event='ready', ns=monotonic_ns())
        await asyncio.to_thread(sys.stdin.readline)
        tracks = []
        if args.role == 'subscriber':
            for index in range(args.tracks):
                track = SubscribedTrack(session, NAMESPACE, f'track-{index}',
                    on_object=lambda *fields, i=index: receive(i, *fields))
                await track.subscribe(forward=None, group_order=GroupOrder.ASCENDING)
                tracks.append(track)
        elif args.role == 'publisher':
            async with asyncio.timeout(15):
                while len(requests) != args.tracks:
                    await asyncio.sleep(.01)
        emit(event='established', ns=monotonic_ns())
        await asyncio.to_thread(sys.stdin.readline)
        if args.active and args.role == 'publisher':
            streams = []
            for index in range(args.tracks):
                _, alias = requests[f'track-{index}'.encode()]
                stream = await session.open_uni_stream()
                header = SubgroupHeader(track_alias=alias, group_id=0, subgroup_id=0,
                                        publisher_priority=128, prof=profile_for(22))
                session.stream_write(stream, header.serialize().data)
                streams.append((stream, header))
            started = monotonic_ns()
            emit(event='send_start', ns=started)
            for number in range(args.objects):
                target = started + number * args.interval_ms * 1_000_000
                await asyncio.sleep(max(0, (target - monotonic_ns()) / 1e9))
                for stream, header in streams:
                    buf = header.next_object(payload=b't' * args.payload, object_id=number)
                    await session.stream_write_drain(stream, buf.data)
            # Leave the subscription and streams open for delivery verification and
            # resource sampling. Termination is measured after the controller releases us.
            emit(event='sent', ns=monotonic_ns(), objects=args.objects * args.tracks)
            await asyncio.to_thread(sys.stdin.readline)
            for stream, _ in streams:
                session.stream_write(stream, b'', end_stream=True)
            for request_id, _ in requests.values():
                session.subscribe_done(request_id=request_id,
                    status_code=SubscribeDoneCode.TRACK_ENDED, stream_count=1,
                    reason='measurement complete')
            await asyncio.sleep(.2)
        elif args.active and args.role == 'subscriber':
            async with asyncio.timeout(args.objects * args.interval_ms / 1000 + 15):
                while len(seen) < args.objects * args.tracks:
                    await asyncio.sleep(.01)
            emit(event='received', ns=monotonic_ns(), first_ns=first,
                 objects=len(seen), errors=errors)
            await asyncio.to_thread(sys.stdin.readline)
        else:
            await asyncio.to_thread(sys.stdin.readline)


async def trial(args, relay_name, level, block, position, work):
    tracks = level if args.mode == 'active' else 1
    extras = level if args.mode == 'idle' else 0
    def report(**row):
        emit(mode=args.mode, relay=relay_name, level=level, block=block,
             position=position, tracks=tracks, extra_connections=extras, **row)
    async with AsyncExitStack() as stack:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.bind(('127.0.0.1', args.port))
        relay = await asyncio.create_subprocess_exec(*relay_command(relay_name, args.port, work),
                                                      cwd=work, stdout=sys.stderr)
        stack.push_async_callback(stop, relay)
        async with asyncio.timeout(5):
            while args.port not in udp_ports(relay.pid):
                if relay.returncode is not None:
                    raise RuntimeError('Relay exited')
                await asyncio.sleep(.02)
        roles = {'relay': relay}
        for role in ['publisher', 'subscriber'] + [f'idle-{i}' for i in range(extras)]:
            child = await asyncio.create_subprocess_exec(sys.executable, __file__,
                '--role', role.split('-')[0], '--port', str(args.port), '--cert', str(work/'cert.pem'),
                '--tracks', str(tracks), '--objects', str(args.objects),
                '--payload', str(args.payload), '--interval-ms', str(args.interval_ms),
                *(['--active'] if args.mode == 'active' else []),
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE)
            roles[role] = child
            stack.push_async_callback(stop, child)
            await read_until(child, role, 'ready', report)
        for role, child in roles.items():
            if role != 'relay':
                await command(child)
        for role, child in roles.items():
            if role != 'relay':
                await read_until(child, role, 'established', report)
        await asyncio.sleep(.5)
        before = {role: snapshot(child.pid) for role, child in roles.items()}
        started = monotonic_ns()
        for role, child in roles.items():
            if role != 'relay':
                await command(child)
        observations = {role: [] for role in roles}
        duration = args.duration if args.mode == 'active' else args.idle_seconds
        while monotonic_ns() - started < duration * 1e9:
            for role, child in roles.items():
                memory, cpu, tids = snapshot(child.pid)
                observations[role].append((monotonic_ns(), memory, cpu, tids))
            await asyncio.sleep(.25)
        for role, samples in observations.items():
            end, memory, cpu, tids = samples[-1]
            _, prior, old_tids = before[role]
            report(event='resource', role=role, window_ns=end-started,
                   cpu_ns=cpu-prior if all(s[3] == old_tids for s in samples) else None,
                   pss_start_kib=before[role][0]['pss_kib'],
                   pss_end_kib=memory['pss_kib'],
                   rss_start_kib=before[role][0]['rss_kib'],
                   rss_end_kib=memory['rss_kib'],
                   series=[{'elapsed_ns': t-started, **m, 'cpu_ns': c-prior,
                            'cpu_valid': tids_at_sample == old_tids}
                           for t, m, c, tids_at_sample in samples],
                   pss_max_sampled_kib=max(s[1]['pss_kib'] for s in samples),
                   rss_max_sampled_kib=max(s[1]['rss_kib'] for s in samples),
                   samples=len(samples))
        if args.mode == 'active':
            # The sender emits send_start before sent; retain both events.
            async with asyncio.timeout(15):
                sent = await read_until(roles['publisher'], 'publisher', 'sent', report)
                received = await read_until(roles['subscriber'], 'subscriber', 'received', report)
            if sent['objects'] != received['objects'] or received['errors']:
                raise RuntimeError('Payload verification failed')
        ports = {role: udp_ports(child.pid) for role, child in roles.items() if role != 'relay'}
        for role in ['publisher'] + [r for r in roles if r not in ('relay', 'publisher')]:
            child = roles[role]
            await command(child)
            await asyncio.wait_for(child.wait(), 5)
            if child.returncode:
                raise RuntimeError(f'{role} exited {child.returncode}')
        report(event='trial_completed', passed=True)
        return ports


async def run(args):
    rng = random.Random(22022)
    cases = []
    levels = args.levels or ([0, 1, 2, 3] if args.mode == 'idle' else [1, 4])
    orders = list(itertools.permutations(RELAYS)) if args.balanced else [RELAYS]
    rng.shuffle(orders)
    for block, order in enumerate(orders, 1):
        block_levels = list(levels)
        rng.shuffle(block_levels)
        cases.extend((level, block, order) for level in block_levels)
    emit(event='configuration', cpu_counter='linux-process-clock', mode=args.mode, levels=levels, objects=args.objects,
         payload=args.payload, interval_ms=args.interval_ms, duration=args.duration,
         idle_seconds=args.idle_seconds, seed=22022, balanced=args.balanced)
    failures = 0
    with tempfile.TemporaryDirectory(prefix='moqt-resources-') as directory:
        work = Path(directory)
        subprocess.run(['openssl','req','-x509','-newkey','ec','-pkeyopt',
            'ec_paramgen_curve:P-256','-noenc','-days','1','-subj','/CN=localhost',
            '-addext','subjectAltName=IP:127.0.0.1','-keyout',str(work/'key.pem'),
            '-out',str(work/'cert.pem')],check=True,stderr=subprocess.DEVNULL)
        for level, block, order in cases:
            for position, relay in enumerate(order, 1):
                try:
                    if args.capture:
                        with capture_links(args.port) as links:
                            ports = await trial(args, relay, level, block, position, work)
                        used = set()
                        for role, candidates in ports.items():
                            matched = candidates & links.keys()
                            if len(matched) != 1:
                                raise RuntimeError(f'Cannot attribute traffic to {role}')
                            peer = matched.pop()
                            used.add(peer)
                            tx, tx_bytes, rx, rx_bytes = links[peer]
                            emit(event='wire', mode=args.mode, relay=relay, level=level,
                                 block=block, position=position, role=role,
                                 tx_datagrams=tx, tx_udp_bytes=tx_bytes,
                                 rx_datagrams=rx, rx_udp_bytes=rx_bytes)
                        if used != links.keys():
                            raise RuntimeError('Unattributed traffic')
                    else:
                        await trial(args, relay, level, block, position, work)
                except Exception as error:
                    failures += 1
                    emit(event='trial_failed', mode=args.mode, relay=relay,
                         level=level, block=block, position=position,
                         error=type(error).__name__ + ': ' + str(error))
    if failures:
        raise RuntimeError(f'{failures} trials failed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('idle','active'), default='idle')
    parser.add_argument('--role', choices=('publisher','subscriber','idle'))
    parser.add_argument('--cert')
    parser.add_argument('--port', type=int, default=45453)
    parser.add_argument('--tracks', type=int, default=1)
    parser.add_argument('--levels', nargs='+', type=int)
    parser.add_argument('--balanced', action='store_true')
    parser.add_argument('--capture', action='store_true')
    parser.add_argument('--active', action='store_true')
    parser.add_argument('--duration', type=float, default=30)
    parser.add_argument('--idle-seconds', type=float, default=5)
    parser.add_argument('--objects', type=int, default=1500)
    parser.add_argument('--payload', type=int, default=8192)
    parser.add_argument('--interval-ms', type=int, default=20)
    args = parser.parse_args()
    if args.duration <= 0 or args.idle_seconds <= 0 or args.objects <= 0:
        parser.error('Durations and object count must be positive')
    if args.mode == 'active' and not args.role and args.objects * args.interval_ms / 1000 < args.duration:
        parser.error('Active workload must cover the observation interval')
    asyncio.run(endpoint(args) if args.role else run(args))

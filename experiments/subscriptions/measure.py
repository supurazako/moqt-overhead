"""Pilot: vary idle subscriptions on one fixed Publisher/Subscriber connection pair."""

import argparse
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
from time import monotonic_ns

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'experiments/fanout'))
from measure import command, emit, read_until, relay_command, snapshot, stop
from aiomoqt.client import MOQTClient
from aiomoqt.track import SubscribedTrack
from aiomoqt.types import GroupOrder, MOQTMessageType

RELAYS = ('aiomoqt', 'imquic', 'moqtail')
NAMESPACE = 'moq-test/subscriptions'


async def endpoint(args):
    logging.disable(logging.INFO)
    client = MOQTClient('127.0.0.1', args.port, use_quic=True,
                        ca_file=args.cert, supported_drafts=22)
    accepted = set()

    async def on_subscribe(session, msg):
        session.subscribe_ok(request_msg=msg)
        accepted.add(bytes(msg.track_name))

    if args.role == 'publisher':
        client.register_handler(MOQTMessageType.SUBSCRIBE, on_subscribe)
    async with asyncio.timeout(20):
        async with client.connect() as session:
            await session.client_session_init()
            if session.negotiated_draft != 22:
                raise RuntimeError('Unexpected draft')
            if args.role == 'publisher':
                await session.publish_namespace(namespace=NAMESPACE, wait_response=True)
            emit(event='ready')
            if await asyncio.to_thread(sys.stdin.readline) != 'go\n':
                raise RuntimeError('Missing command')
            tracks = []
            if args.role == 'subscriber':
                for number in range(args.count):
                    track = SubscribedTrack(session, NAMESPACE, f'track-{number}')
                    await track.subscribe(forward=None, group_order=GroupOrder.ASCENDING)
                    tracks.append(track)
            else:
                while len(accepted) < args.count:
                    await asyncio.sleep(.01)
            emit(event='established', count=len(tracks) if args.role == 'subscriber' else len(accepted))
            await asyncio.to_thread(sys.stdin.readline)


async def trial(args, name, count, block, position, work):
    def report(**fields):
        emit(relay=name, subscriptions=count, block=block, position=position, **fields)

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.bind(('127.0.0.1', args.port))
    async with AsyncExitStack() as stack:
        relay = await asyncio.create_subprocess_exec(
            *relay_command(name, args.port, work), cwd=work, stdout=sys.stderr)
        stack.push_async_callback(stop, relay)
        async with asyncio.timeout(5):
            while args.port not in [int(line.split()[1].split(':')[1], 16)
                                   for table in ('udp', 'udp6')
                                   for line in Path(f'/proc/net/{table}').read_text().splitlines()[1:]]:
                if relay.returncode is not None:
                    raise RuntimeError('Relay exited')
                await asyncio.sleep(.02)
        roles = {'relay': relay}
        for role in ('publisher', 'subscriber'):
            child = await asyncio.create_subprocess_exec(
                sys.executable, __file__, '--role', role, '--count', str(count),
                '--port', str(args.port), '--cert', str(work/'cert.pem'),
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE)
            stack.push_async_callback(stop, child)
            roles[role] = child
            await read_until(child, role, 'ready', report)

        async def sample(phase):
            await asyncio.sleep(.5)
            before = {role: snapshot(child.pid) for role, child in roles.items()}
            start = monotonic_ns()
            await asyncio.sleep(1)
            for role, child in roles.items():
                memory, cpu, tids = snapshot(child.pid)
                _, prior, old_tids = before[role]
                report(event='sample', phase=phase, role=role, window_ns=monotonic_ns()-start,
                       cpu_ns=cpu-prior if tids == old_tids else None, **memory)

        await sample('setup')
        for role in ('publisher', 'subscriber'):
            await command(roles[role])
        for role in ('publisher', 'subscriber'):
            event = await read_until(roles[role], role, 'established', report)
            if event['count'] != count:
                raise RuntimeError('Subscription count mismatch')
        await sample('subscribed')
        report(event='trial_completed', passed=True)
        for role in ('subscriber', 'publisher'):
            await command(roles[role])
            await asyncio.wait_for(roles[role].wait(), 3)


async def run(args):
    rng = random.Random(22)
    cases = []
    for count in args.counts:
        orders = list(itertools.permutations(RELAYS)) if args.pilot else [RELAYS]
        rng.shuffle(orders)
        cases.extend((count, block, order) for block, order in enumerate(orders, 1))
    rng.shuffle(cases)
    failures = 0
    with tempfile.TemporaryDirectory(prefix='moqt-subscriptions-') as directory:
        work = Path(directory)
        subprocess.run(['openssl','req','-x509','-newkey','ec','-pkeyopt',
                        'ec_paramgen_curve:P-256','-noenc','-days','1','-subj','/CN=localhost',
                        '-addext','subjectAltName=IP:127.0.0.1','-keyout',str(work/'key.pem'),
                        '-out',str(work/'cert.pem')],check=True,stderr=subprocess.DEVNULL)
        for count, block, order in cases:
            for position, name in enumerate(order, 1):
                try:
                    await trial(args, name, count, block, position, work)
                except Exception as error:
                    emit(relay=name, subscriptions=count, block=block, position=position,
                         event='trial_failed', error=str(error))
                    failures += 1
    if failures:
        raise RuntimeError(f'{failures} trials failed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--role', choices=('publisher','subscriber'))
    parser.add_argument('--cert')
    parser.add_argument('--port',type=int,default=45451)
    parser.add_argument('--count',type=int,default=1)
    parser.add_argument('--counts',nargs='+',type=int,choices=range(5),default=list(range(5)))
    parser.add_argument('--pilot',action='store_true')
    args=parser.parse_args()
    asyncio.run(endpoint(args) if args.role else run(args))

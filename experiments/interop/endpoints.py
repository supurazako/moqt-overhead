"""Qualify separate Publisher and Subscriber processes with certificate validation."""

import argparse
import asyncio
import json
import sys
from contextlib import AsyncExitStack
from time import monotonic_ns

from aiomoqt.client import MOQTClient
from aiomoqt.tools.moq_interop_client import (
    DATA_SUBGROUP_BASIC_CASE,
    _DATA_DELIVERY_S,
    _PUB_NS_PARAMS,
    _DataPublisher,
    _DataSubscriber,
    _data_problems,
)
from aiomoqt.track import SubscribedTrack
from aiomoqt.types import GroupOrder, MOQTMessageType

NAMESPACE = ("moq-test", "split-endpoints")
TRACK = "track"


def event(name, **fields):
    print(json.dumps({"event": name, "monotonic_ns": monotonic_ns(), **fields}), flush=True)


async def endpoint(role, port, cert):
    client = MOQTClient("127.0.0.1", port, use_quic=True, ca_file=cert, supported_drafts=22)
    if role == "publisher":
        publisher = _DataPublisher(tuple(part.encode() for part in NAMESPACE), TRACK.encode())
        client.register_handler(MOQTMessageType.SUBSCRIBE, publisher.on_subscribe)

    async with asyncio.timeout(15):
        event("connect_start")
        async with client.connect() as session:
            event("quic_connected")
            await session.client_session_init()
            if session.negotiated_draft != 22:
                raise RuntimeError("Unexpected MoQT draft")
            event("setup_done")
            if role == "publisher":
                await session.publish_namespace(namespace="/".join(NAMESPACE),
                                                parameters=_PUB_NS_PARAMS, wait_response=True)
                event("namespace_published")
                await publisher.subscribed.wait()
                if publisher.forward == 0:
                    raise RuntimeError("Upstream forwarding is disabled")
                event("send_start")
                streams = await publisher.send(session)
                if not publisher.done_sent:
                    raise RuntimeError("Publisher did not send PUBLISH_DONE")
                event("send_done", streams=streams)
                await asyncio.to_thread(sys.stdin.readline)
            else:
                subscriber = _DataSubscriber()

                def on_object(*args):
                    if not subscriber.objects:
                        event("first_object")
                    subscriber.on_object(*args)

                track = SubscribedTrack(
                    session, "/".join((*NAMESPACE, *DATA_SUBGROUP_BASIC_CASE)),
                    TRACK, on_object=on_object, on_done=subscriber.on_done,
                )
                await track.subscribe(forward=None, group_order=GroupOrder.ASCENDING)
                event("subscribe_done")
                session.register_stream_end_handler(track.track_alias, subscriber.on_stream_end)
                await subscriber.drain(asyncio.get_running_loop().time() + _DATA_DELIVERY_S)
                problems = _data_problems(subscriber.objects)
                if problems or subscriber.done is None or subscriber.streams_ended != 3:
                    raise RuntimeError(f"Transfer validation failed: {problems}")
                event("receive_done", objects=len(subscriber.objects), streams=subscriber.streams_ended)


async def collect(child, role, ready):
    async for line in child.stdout:
        row = json.loads(line)
        print(json.dumps({"role": role, **row}), flush=True)
        if row["event"] == "namespace_published":
            ready.set()
    if await child.wait():
        raise RuntimeError(f"{role} process failed")


async def run(port, cert):
    async with AsyncExitStack() as children:
        async def launch(role):
            child = await asyncio.create_subprocess_exec(
                sys.executable, __file__, str(port), cert, "--role", role,
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            )

            async def stop():
                if child.returncode is None:
                    child.kill()
                    await child.wait()

            children.push_async_callback(stop)
            return child

        async with asyncio.timeout(20):
            ready = asyncio.Event()
            publisher = await launch("publisher")
            async with asyncio.TaskGroup() as tasks:
                publishing = tasks.create_task(collect(publisher, "publisher", ready))
                await ready.wait()
                subscriber = await launch("subscriber")
                await collect(subscriber, "subscriber", ready)
                publisher.stdin.write(b"\n")
                await publisher.stdin.drain()
                await publishing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port", type=int)
    parser.add_argument("cert")
    parser.add_argument("--role", choices=("publisher", "subscriber"))
    args = parser.parse_args()
    if args.role:
        asyncio.run(endpoint(args.role, args.port, args.cert))
    else:
        asyncio.run(run(args.port, args.cert))


if __name__ == "__main__":
    main()

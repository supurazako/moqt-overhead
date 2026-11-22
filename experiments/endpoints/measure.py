"""Measure candidate Pub/Sub processes, keeping relay and peer fixed."""
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
from contextlib import AsyncExitStack
from pathlib import Path
from time import monotonic_ns

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from experiments.resources.measure import snapshot
from experiments.fanout.measure import relay_command, stop, udp_ports
from aiomoqt.client import MOQTClient
from aiomoqt.track import SubscribedTrack
from aiomoqt.tools.moq_interop_client import _DataPublisher
from aiomoqt.types import MOQTMessageType, GroupOrder

CASE=('moq-test-00','0','0','0','0','49','50','64','64','100','1','1','0','-1','-1','0')
NAMESPACE='/'.join(CASE)
IMPLEMENTATIONS=('imquic','moqtail','aiomoqt')


def event(name, **fields):
    print('BENCH_'+name+(' '+json.dumps(fields) if fields else ''),flush=True)


async def endpoint(args):
    logging.disable(logging.INFO)
    client=MOQTClient('127.0.0.1',args.port,use_quic=True,
                      ca_file=args.cert,supported_drafts=22)
    publisher=_DataPublisher((),b'track')
    if args.role=='publisher':
        client.register_handler(MOQTMessageType.SUBSCRIBE,publisher.on_subscribe)
    async with client.connect() as session:
        await session.client_session_init()
        if session.negotiated_draft!=22: raise RuntimeError('Unexpected draft')
        if args.role=='publisher':
            await session.publish_namespace(namespace='moq-test-00',wait_response=True)
            event('READY')
            await publisher.subscribed.wait()
            if args.gated: await asyncio.to_thread(sys.stdin.readline)
            pending=[]
            original_done=session.subscribe_done
            if args.gated:
                session.subscribe_done=lambda **fields: pending.append(fields)
            await publisher.send(session)
            event('SENT')
            if args.gated:
                await asyncio.to_thread(sys.stdin.readline)
                for fields in pending: original_done(**fields)
                return
        else:
            seen=set(); errors=0; done=asyncio.Event()
            def receive(msg,size,stamp,group,subgroup):
                nonlocal errors
                if not msg.payload: return
                if (group!=0 or subgroup!=0 or msg.object_id in seen
                    or msg.object_id not in range(50) or msg.payload!=b't'*64): errors+=1
                seen.add(msg.object_id)
                if len(seen)==50: done.set()
            track=SubscribedTrack(session,NAMESPACE,'track',on_object=receive)
            await track.subscribe(forward=None,group_order=GroupOrder.ASCENDING)
            event('READY')
            await asyncio.wait_for(done.wait(),15)
            print(f'BENCH_RECEIVED {len(seen)} {errors}',flush=True)
        await asyncio.to_thread(sys.stdin.readline)


def candidate_command(name,role,port,cert):
    if name=='aiomoqt':
        return [sys.executable,__file__,'--role',role,'--port',str(port),'--cert',str(cert)]
    if name=='imquic':
        binary=ROOT/'.scratch/endpoint-built'/('imquic-bench-pub' if role=='publisher' else 'imquic-bench-sub')
        command=[str(binary),'-M','22','-q','-r','127.0.0.1','-R',str(port),'-S','localhost','-d','0']
        if role=='subscriber':
            for part in CASE: command.extend(['-n',part])
            command.extend(['-N','track'])
        return command
    command=[str(ROOT/'.scratch/endpoint-built/moqtail-bench-client'),
             '--transport','quic','--server',f'moqt://127.0.0.1:{port}',
             '--namespace',NAMESPACE,'--track-name','track','--command',
             'publish-namespace' if role=='publisher' else 'subscribe']
    if role=='publisher':
        command+=['--group-count','1','--objects-per-group','50','--payload-size','64','--interval','100']
    else: command+=['--duration','30','--filter','none']
    return command


async def trial(args,name,role,block,position,work):
    def emit(**fields):
        print(json.dumps(dict(implementation=name,role=role,block=block,position=position,**fields)),flush=True)
    async with AsyncExitStack() as stack:
        async def launch(command,env=None):
            child=await asyncio.create_subprocess_exec(*command,cwd=work,env=env,
                  stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,
                  stderr=asyncio.subprocess.PIPE)
            stack.push_async_callback(stop,child)
            events=asyncio.Queue()
            async def read():
                async for line in child.stdout:
                    text=line.decode(errors='replace').strip()
                    if text.startswith('BENCH_'): await events.put(text)
            async def stderr():
                async for line in child.stderr:
                    # Local diagnostics only; published events contain no raw logs.
                    print(line.decode(errors='replace').rstrip(),file=sys.stderr)
            tasks=[asyncio.create_task(read()),asyncio.create_task(stderr())]
            async def finish_readers():
                for task in tasks: task.cancel()
                await asyncio.gather(*tasks,return_exceptions=True)
            stack.push_async_callback(finish_readers)
            async def wait(expected,timeout=12):
                async with asyncio.timeout(timeout):
                    while True:
                        line=await events.get()
                        if line.startswith('BENCH_'+expected): return line
            return child,wait
        relay,_=await launch(relay_command('aiomoqt',args.port,work))
        async with asyncio.timeout(5):
            while args.port not in udp_ports(relay.pid): await asyncio.sleep(.02)
        candidate_ca=work/('untrusted.pem' if args.negative_trust else 'ca.pem')
        env=dict(os.environ,LD_LIBRARY_PATH=str(ROOT/'.scratch/endpoint-built'),
                 MOQ_TEST_CA_FILE=str(candidate_ca),SSL_CERT_FILE=str(candidate_ca),
                 RUST_LOG='error',NO_COLOR='1')
        if role=='subscriber':
            peer,peer_wait=await launch([sys.executable,__file__,'--role','publisher',
                '--gated','--port',str(args.port),'--cert',str(work/'ca.pem')])
            await peer_wait('READY')
        candidate,candidate_wait=await launch(candidate_command(name,role,args.port,candidate_ca),env)
        await candidate_wait('READY',4 if args.negative_trust else 12)
        async def sample(phase,seconds,finished=None):
            before,cpu,_=snapshot(candidate.pid)
            start=monotonic_ns();series=[]
            while monotonic_ns()-start<seconds*1e9:
                memory,used,_=snapshot(candidate.pid)
                series.append(dict(elapsed_ns=monotonic_ns()-start,cpu_ns=used-cpu,**memory))
                await asyncio.sleep(.1)
            final=series[-1]
            emit(event='resource',phase=phase,window_ns=final['elapsed_ns'],
                 cpu_ns=final['cpu_ns'],pss_start_kib=before['pss_kib'],
                 pss_end_kib=final['pss_kib'],pss_max_kib=max(s['pss_kib'] for s in series),
                 rss_max_kib=max(s['rss_kib'] for s in series),
                 thread_count=len(list(Path(f'/proc/{candidate.pid}/task').iterdir())),samples=series)
        await sample('connected_idle',2)
        if role=='publisher':
            peer,peer_wait=await launch([sys.executable,__file__,'--role','subscriber',
                      '--port',str(args.port),'--cert',str(work/'ca.pem')])
            receiver=asyncio.create_task(peer_wait('RECEIVED',15))
        else:
            receiver=asyncio.create_task(candidate_wait('RECEIVED',15))
            peer.stdin.write(b'go\n');await peer.stdin.drain()
        await sample('transfer',5)
        received=await receiver
        parts=received.split()
        if parts!=['BENCH_RECEIVED','50','0']: raise RuntimeError('Delivery validation: '+received)
        emit(event='completed',passed=True,objects=50,payload_bytes=3200)


async def run(args):
    orders=list(itertools.permutations(IMPLEMENTATIONS)) if args.balanced else [IMPLEMENTATIONS]
    rng=random.Random(22023);rng.shuffle(orders)
    roles=args.roles
    with tempfile.TemporaryDirectory(prefix='moqt-endpoints-') as directory:
        work=Path(directory)
        quiet=dict(check=True,stderr=subprocess.DEVNULL,stdout=subprocess.DEVNULL)
        subprocess.run(['openssl','req','-x509','-newkey','ec','-pkeyopt',
             'ec_paramgen_curve:P-256','-noenc','-days','1','-subj','/CN=Benchmark Root',
             '-keyout',str(work/'ca.key'),'-out',str(work/'ca.pem')],**quiet)
        subprocess.run(['openssl','req','-new','-newkey','ec','-pkeyopt',
             'ec_paramgen_curve:P-256','-noenc','-subj','/CN=localhost',
             '-keyout',str(work/'key.pem'),'-out',str(work/'leaf.csr')],**quiet)
        (work/'leaf.ext').write_text('basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\nextendedKeyUsage=serverAuth\nsubjectAltName=DNS:localhost,IP:127.0.0.1\n')
        subprocess.run(['openssl','x509','-req','-in',str(work/'leaf.csr'),
             '-CA',str(work/'ca.pem'),'-CAkey',str(work/'ca.key'),'-CAcreateserial',
             '-days','1','-extfile',str(work/'leaf.ext'),'-out',str(work/'cert.pem')],**quiet)
        if args.negative_trust:
            subprocess.run(['openssl','req','-x509','-newkey','ec','-pkeyopt',
                'ec_paramgen_curve:P-256','-noenc','-days','1','-subj','/CN=Unrelated Root',
                '-keyout',str(work/'untrusted.key'),'-out',str(work/'untrusted.pem')],**quiet)
        failures=0
        for block,order in enumerate(orders,1):
            for role in roles:
                for position,name in enumerate(order,1):
                    try:
                        await trial(args,name,role,block,position,work)
                        if args.negative_trust: raise RuntimeError('Unexpected connection with wrong CA')
                    except Exception as error:
                        if args.negative_trust and isinstance(error,TimeoutError):
                            print(json.dumps(dict(event='expected_no_ready',implementation=name,role=role)),flush=True)
                            continue
                        failures+=1
                        print(json.dumps(dict(event='failed',implementation=name,role=role,
                            block=block,position=position,error=type(error).__name__+': '+str(error))),flush=True)
        if failures: raise RuntimeError(f'{failures} trials failed')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--role',choices=('publisher','subscriber'))
    parser.add_argument('--roles',nargs='+',choices=('publisher','subscriber'),default=['publisher','subscriber'])
    parser.add_argument('--gated',action='store_true')
    parser.add_argument('--port',type=int,default=45457)
    parser.add_argument('--cert')
    parser.add_argument('--balanced',action='store_true')
    parser.add_argument('--negative-trust',action='store_true')
    args=parser.parse_args()
    asyncio.run(endpoint(args) if args.role else run(args))

"""Confirm that the Linux CPU counter retains an exited worker's runtime."""
import importlib.util
import subprocess
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location('resource_measurement', Path(__file__).with_name('measure.py'))
measurement = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measurement)
worker = '''import threading,time,sys
print('ready',flush=True)
sys.stdin.readline()
def work():
    end=time.thread_time()+.08
    while time.thread_time()<end: pass
thread=threading.Thread(target=work)
thread.start();thread.join()
print('done',flush=True)
sys.stdin.readline()
'''
child = subprocess.Popen([sys.executable, '-c', worker], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, text=True)
try:
    assert child.stdout.readline().strip() == 'ready'
    _, before, _ = measurement.snapshot(child.pid)
    child.stdin.write('go\n'); child.stdin.flush()
    assert child.stdout.readline().strip() == 'done'
    _, after, _ = measurement.snapshot(child.pid)
    assert after - before >= 70_000_000
    print(f'Retained process CPU after worker exit: {(after-before)/1e6:.3f} ms')
    child.stdin.write('stop\n'); child.stdin.flush()
    child.wait(timeout=3)
finally:
    if child.poll() is None:
        child.kill()
        child.wait()

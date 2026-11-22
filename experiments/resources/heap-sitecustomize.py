import json,sys,threading,tracemalloc
from pathlib import Path
if '--role' in sys.argv:
    tracemalloc.start(8)
    role=sys.argv[sys.argv.index('--role')+1]
    def report():
        snapshot=tracemalloc.take_snapshot()
        rows=[{'file':Path(s.traceback[0].filename).name,'line':s.traceback[0].lineno,
               'bytes':s.size,'count':s.count} for s in snapshot.statistics('lineno')[:8]]
        print('HEAP '+json.dumps({'role':role,'current_peak':tracemalloc.get_traced_memory(),'top':rows}),file=sys.stderr,flush=True)
    timer=threading.Timer(10,report);timer.daemon=True;timer.start()

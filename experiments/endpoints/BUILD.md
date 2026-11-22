# Rebuild the endpoint adapters

Requirements: Docker with the pinned base image from
[interop setup](../interop/README.md), Rust/Cargo 1.98.0, clang 19 and a C
linker. Work in the study repository root. Start with a fresh MOQtail checkout;
patch commands intentionally fail if the adapters have already been applied.

```sh
git clone --depth 1 --branch 'client@0.17.0' \
  https://github.com/moqtail/moqtail.git .scratch/endpoint-moqtail
patch -p1 -d .scratch/endpoint-moqtail/apps/client/src < experiments/endpoints/publisher.rs.patch
patch -p1 -d .scratch/endpoint-moqtail/apps/client/src < experiments/endpoints/subscriber.rs.patch
patch -p1 -d .scratch/endpoint-moqtail/apps/client/src < experiments/endpoints/connection.rs.patch
CC=clang CXX=clang++ cargo build \
  --manifest-path .scratch/endpoint-moqtail/Cargo.toml --release --locked -p client -j 4
mkdir -p .scratch/endpoint-built
cp .scratch/endpoint-moqtail/target/release/client .scratch/endpoint-built/moqtail-bench-client

docker build -t moqt-overhead-endpoints:d93d181 \
  -f experiments/endpoints/imquic.Dockerfile experiments/endpoints
```

Extract the native C executables and their rebuilt shared library:

```sh
python3 - <<'PY'
import subprocess
from pathlib import Path
out=Path('.scratch/endpoint-built')
container=subprocess.check_output(['docker','create','moqt-overhead-endpoints:d93d181'],text=True).strip()
try:
    for source,target in [
        ('examples/.libs/imquic-moq-test','imquic-bench-pub'),
        ('examples/.libs/imquic-moq-sub','imquic-bench-sub'),
        ('src/.libs/libimquic.so.0.0.2','libimquic.so.0'),
    ]:
        subprocess.run(['docker','cp',f'{container}:/build/imquic/{source}',str(out/target)],check=True)
finally:
    subprocess.run(['docker','rm',container],check=True)
PY
```

The measured C artifacts were rebuilt using the same three source changes
inside an ephemeral container from the same base image. The Dockerfile
above expresses that rebuild declaratively. Host runtime libraries still
matter when the extracted binaries run natively. Compare source hashes,
versions and behavior; bit-for-bit identity of independent builds is not
assumed.

[Run and measure](README.md).

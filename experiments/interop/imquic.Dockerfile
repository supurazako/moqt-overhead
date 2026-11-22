FROM debian:13@sha256:9c6e381421d0f48d1b8133e573f33c185ee16cbf505eda9c4a8a4791b25ea8a6

RUN apt-get update && apt-get install -y --no-install-recommends \
    autoconf automake build-essential ca-certificates cmake git libglib2.0-dev \
    libjansson-dev libssl-dev libtool pkg-config && rm -rf /var/lib/apt/lists/*

WORKDIR /build/imquic
RUN git init -q && git fetch --depth 1 https://github.com/meetecho/imquic d93d18141b0db5f167290a6b162b059dc964015e \
    && git checkout -q --detach FETCH_HEAD \
    && git init -q picoquic \
    && git -C picoquic fetch --depth 1 https://github.com/private-octopus/picoquic f506de8f8bc92bc06b4920ca2ad5100c8b834f2e \
    && git -C picoquic checkout -q --detach FETCH_HEAD
RUN cmake -S picoquic -B picoquic -DCMAKE_POSITION_INDEPENDENT_CODE=ON -DPICOQUIC_FETCH_PTLS=Y \
    && cmake --build picoquic --parallel 4 \
    && sh autogen.sh && ./configure --enable-moq-examples && make -j4
ENTRYPOINT ["/build/imquic/examples/imquic-moq-relay"]

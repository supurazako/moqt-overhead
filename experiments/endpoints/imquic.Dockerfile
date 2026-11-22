FROM moqt-overhead-imquic:d93d181
COPY moq-test.c.patch moq-sub.c.patch quic.c.patch /patches/
RUN cd /build/imquic/examples && patch -p1 < /patches/moq-test.c.patch \
    && patch -p1 < /patches/moq-sub.c.patch \
    && cd /build/imquic/src && patch -p1 < /patches/quic.c.patch \
    && cd /build/imquic && make -j4

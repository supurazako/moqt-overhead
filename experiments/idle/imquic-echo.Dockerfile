FROM moqt-overhead-imquic:d93d181
RUN ./configure --enable-moq-examples --enable-echo-examples && make -j4
ENTRYPOINT ["/build/imquic/examples/imquic-echo-server"]

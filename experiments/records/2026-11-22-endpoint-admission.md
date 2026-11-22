# Endpoint implementation admission and scope correction

The user clarified that this stage should measure how resource-efficient
existing Publisher/Subscriber implementations are on a PC, rather than
flash hardware or cross-compile firmware. The user also requested
well-known implementations alongside lightweight candidates.

## Admitted resource arms

- imquic C sample origin/subscriber, pinned to `d93d181`.
- MOQtail Rust client 0.17.0, pinned to `2c3efc6`.
- aiomoqt 0.14.1 / aiopquic 0.7.1 Python adapters as a reference.

Each passed Publisher and Subscriber admission against one common external
aiomoqt relay, with strict draft-22, validated server certificates and
50 correct 64-byte Objects. Candidate role processes are separate from
the relay and common counterpart. Measurement details and patches are in
[the endpoint procedure](../endpoints/README.md).

## Other inspected candidates

- Meta moxygen at `00f2d74b345a0fe10ca518f5e6f8ced7d09c018e`:
  current README describes draft-16/18, while the actual version header
  also includes partial draft-22 using Meta-scoped ALPN. Public interop
  image `ghcr.io/facebookexperimental/moxygen-interop-client` was retrieved
  at that commit with digest
  `sha256:66bbdddbec4409d4a6c6026ff20afc172896316385372b5a78d71c953511966d`.
  Its CLI supports control test cases and versions, but has no standalone
  50-Object Pub/Sub role mode. Some cases create publishing and subscribing
  sessions in the same executable. It is not
  treated as an independently measured Publisher or Subscriber. This is
  a harness admission limitation, not proof that its endpoint API cannot
  be used to build separate applications.
- libquicr at `cc5530ead448ffb59e08a6ce960e499e1d29c39f`: targets
  draft-18 in the inspected README. It is excluded from draft-22 resource
  comparisons, without claiming that it is unsuitable for embedded use.
- ESP32-related QUIC and older MoQ application sources were also found.
  The Hactar project pins a draft-16 libquicr component. A cached search
  description of quicr-rs's ESP-IDF feature did not match its current
  checked-out source. These findings supersede earlier blanket statements
  about there being no embedded implementation; they do not establish a
  ready draft-22 MCU endpoint. No MCU build/run was used as study evidence.

## Admission attempts and corrections

1. MOQtail's `v0.17.0` tag did not exist; the correct `client@0.17.0` tag
   resolved to the previously tested relay/library commit.
2. Its client image could not be retrieved anonymously (registry denied),
   so the pinned client was built from source with its lockfile.
3. The initial self-signed test certificate was a CA certificate used as a
   leaf. Rust rejected it with `CaUsedAsEndEntity`. A separate CA and a
   CA:FALSE serverAuth leaf resolved that mismatch.
4. `SSL_CERT_FILE` was insufficient for MOQtail because wtransport 0.7.2's
   `build_native_cert_store()` temporarily removes SSL_CERT_FILE and
   SSL_CERT_DIR. An explicit single-root adapter was added; certificate
   verification was not disabled.
5. imquic sample clients originally hard-code no verification. The measured
   adapters enable it and expose the existing picoquic root-trust setting
   through a test environment variable. The protocol flow is unchanged.
6. With the final adapters, all six trusted role checks passed. Giving the
   three Publisher implementations an unrelated root produced no READY
   marker, with CRYPTO_ERROR/UnknownIssuer diagnostics. No resource values
   from those expected failures enter the balanced sample.

Native adapters also add minimal readiness/receipt events and validation.
The Rust Publisher uses the same constant payload as the C/Python programs
instead of its original PRNG. There is no claim of an optimized MCU port.

Initial check outcomes and the unrelated-root observations are retained
separately from balanced measurements. Raw local stderr can contain local
paths and is not published.

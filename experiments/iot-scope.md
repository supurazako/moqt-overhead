# MCU feasibility: scope and initial evidence

Status: deferred background investigation as of 2026-11-22. No MCU measurements have been made.

The active project has returned to measuring the fixed resource usage and incremental overhead of existing MoQT implementations on Linux, leading to an English blog post. The device candidates and pilot conditions below are retained as historical proposals, not active experiments or hardware purchase requirements.

## Research question

Which workloads can MoQT support on ESP32- and Pico-class microcontrollers, and which resources limit it compared with WebSocket and WebRTC?

- Protocol: retain IETF MoQT draft-22 over raw QUIC as the primary series.
- Interpretation: distinguish implementation availability from demonstrated resource limits. A failed port does not establish a protocol minimum.
- Existing desktop results: evidence about the tested server implementations and configurations, not MCU memory requirements.

## Device families

- ESP32-S3:
  - Dual-core processor up to 240 MHz; 512 KB internal SRAM; Wi-Fi.
  - External PSRAM depends on the module. Record the exact board, module, flash, PSRAM, SDK and configuration.
  - Candidate for the first endpoint investigation because Espressif supplies WebSocket and WebRTC software. This does not establish MoQT feasibility.
  - Compare internal-only and PSRAM-enabled configurations where supported. External RAM does not replace all internal allocation requirements.
  - Sources: [SoC specifications](https://www.espressif.com/en/products/socs/esp32-s3), [external RAM constraints](https://docs.espressif.com/projects/esp-idf/en/latest/esp32s3/api-guides/external-ram.html).
- Raspberry Pi Pico W:
  - RP2040; 264 kB SRAM; 2 MB flash; wireless connectivity.
- Raspberry Pi Pico 2 W:
  - RP2350; 520 kB SRAM; 4 MB flash; processor up to 150 MHz; wireless connectivity.
  - These are microcontrollers, unlike Linux-based Raspberry Pi computers. The W suffix matters for wireless connectivity.
  - Sources: [Pico series](https://www.raspberrypi.com/documentation/microcontrollers/pico-series.html), [Pico 2 specifications](https://www.raspberrypi.com/products/raspberry-pi-pico-2/).
- Arduino:
  - A board/software ecosystem rather than one resource class; ESP32-based boards can also use Arduino software.
  - Nano ESP32: ESP32-S3, 512 kB internal SRAM and 8 MB PSRAM. This overlaps the ESP32-S3 device family rather than providing an independent MCU architecture. Source: [Nano ESP32 manual](https://docs.arduino.cc/tutorials/nano-esp32/cheat-sheet).
  - GIGA R1 WiFi: STM32H747, Cortex-M7 up to 480 MHz and Cortex-M4 up to 240 MHz, 1 MB internal SRAM and 8 MB external SDRAM. This is a higher-resource MCU candidate. Check allocator access, core partitioning and networking support before treating all RAM as available to one protocol stack. Source: [GIGA manual](https://docs.arduino.cc/tutorials/giga-r1-wifi/cheat-sheet).
  - Portenta H7: another STM32H747-based candidate, with 8 MB external SDRAM. Record the exact variant and connectivity. Source: [Portenta H7 family datasheet](https://docs.arduino.cc/resources/datasheets/ABX00042-ABX00045-ABX00046-datasheet.pdf).
  - Do not use UNO R4 WiFi alone as a representative Arduino resource budget. Keep higher-resource MCU candidates in scope; no board is selected for purchase yet.
  - UNO R4 WiFi is one example: its RA4M1 application MCU has 32 kB SRAM, 256 kB flash and a 48 MHz clock. A separate ESP32-S3 provides connectivity.
  - Identify which processor terminates encryption and runs each protocol. Do not add the processors' RAM together or report offloaded communication as application-MCU execution.
  - Source: [UNO R4 WiFi hardware](https://docs.arduino.cc/hardware/uno-r4-wifi/).
- Capacity caveat:
  - These are nominal capacities, not free application memory. Firmware, radio, networking, stacks and buffers consume part of them.
  - Flash stores code/data; RAM holds working state. Record both, with internal RAM and PSRAM separate.

## Workload candidates

These are hypotheses about useful scenarios, not established MoQT deployments or fixed benchmark parameters.

- Sensor readings and commands:
  - Example: a sensor publishes timestamped readings to a dashboard; a device receives configuration commands.
  - Start with synthetic readings to separate transport from sensors and codecs.
  - Candidates: MoQT and secure WebSocket (WSS). Investigate MQTT and CoAP as IoT-specific alternatives before fixing this comparison.
  - Decide whether every sample must arrive or whether newer samples supersede old ones; commands may require different delivery guarantees.
  - Compare persistent connections and reconnecting operation separately, including connection energy where measurable.
- Live audio:
  - Example: a microphone sends audio for remote monitoring, or a device receives spoken output.
  - Candidates: MoQT, WebRTC media and WSS carrying the same encoded frames where feasible.
  - Separate transport-only inputs from capture, encoding, decoding and playback. Record framing, buffering and latency requirements.
- Camera images:
  - Example: a small camera provides periodic JPEG images or a live image stream.
  - Separate JPEG/MJPEG from encoded video. Do not equate JPEG over a WebRTC DataChannel with an RTP video-codec path.
  - MoQT, WSS and WebRTC are endpoint candidates subject to port and hardware support.
  - HLS/LL-HLS are initially gateway/server distribution candidates. Record the MCU-to-gateway transport and any transcoding separately.

## Software evidence and open questions

- WebSocket:
  - Espressif provides an ESP-IDF client component: [esp_websocket_client](https://github.com/espressif/esp-protocols/blob/master/components/esp_websocket_client/README.md).
  - Use WSS for the encrypted comparison. Choose and pin a buildable version before qualification.
- WebRTC:
  - Espressif supplies an embedded solution with media and DataChannel paths: [official overview](https://docs.espressif.com/projects/esp-adf/en/latest/solution-center/esp-webrtc-solution.html).
  - Its `esp_peer` README claims a minimal configuration below 60 KB RAM. This is an upstream component claim, not our measurement or a complete application peak; do not compare it directly with desktop PSS or total board SRAM.
  - Source: [component requirements](https://github.com/espressif/esp-webrtc-solution/blob/main/components/esp_peer/README.md).
  - An ESP32-S3 JPEG example exists: [local_jpeg_stream](https://github.com/espressif/esp-webrtc-solution/blob/main/solutions/local_jpeg_stream/README.md). Hardware and configuration remain to be qualified.
- MoQT:
  - MCU-capable draft-22 endpoint and QUIC/TLS stack selection remains open.
  - Desktop C implementation availability alone does not establish MCU support. Check OS assumptions, timers, sockets, allocator, TLS 1.3, build dependencies and memory limits.
  - Treat moq-lite or other draft versions as separate series if investigated.
- Pico and Arduino:
  - Endpoint libraries, TLS/QUIC support and buildable configurations remain to be investigated. No claim of support or impossibility is made here.

## Architecture and measurements

- Initial architecture: MCU Publisher or Subscriber; external relay/gateway; PC/browser counterpart. Measure the roles separately.
- RAM: static allocation, heap peak, task stack high-water marks and largest free block; distinguish internal/external RAM and avoid double counting.
- Flash: firmware size and required partitions, including update space if the chosen application requires it.
- CPU: processing time and missed application deadlines, alongside achieved transfer rate and losses.
- Network: application bytes and total traffic; report whether Wi-Fi link overhead is observed.
- Timing: cold start, encrypted connection, subscription, first data, steady delivery and reconnect.
- Energy: connection and steady-operation energy, plus duty-cycle assumptions, only when suitable hardware measurement is available.
- Phases: boot, radio ready, encrypted transport ready, application session ready, active transfer, disconnect/reconnect.
- Controls: radio/network baseline, encrypted transport baseline where available, protocol with synthetic data, complete application.
- Comparison: align encryption/authentication, payload, delivery policy, buffer limits and topology. Account for WebRTC signaling, ICE and TURN if used; distinguish WSS TCP/TLS and MoQT QUIC/TLS setup.
- Experimental design: adapt the existing balanced, repeated design to MCU resets, thermal state and connection history. Fix workload, duration, success criteria and repeat count after a pilot, before the main measurement.
- Success: complete the declared workload within its resource and timing budget. Define these budgets per scenario before measurement; nominal SRAM capacity alone is insufficient.
- Failure labels: unsupported platform, unsupported draft/feature, build failure, connection failure, allocation failure, deadline failure, or incorrect delivery. Record evidence before attributing cause.

## Next steps

### Proposed pilot conditions

- Status: proposed settings, not a preregistered main experiment or representative real-world traffic. Qualify implementations first.
- Boards: start with one ESP32-S3 board, potentially Nano ESP32; compare external-RAM-disabled and enabled configurations on the same hardware. Then investigate one STM32H747 board such as GIGA R1 WiFi. Pico 2 W remains conditional on software support. Cross-board differences cannot isolate RAM capacity alone.
- Roles: one MCU endpoint, one external relay and one PC counterpart; one connection and one track-equivalent. Test MCU publishing and subscribing separately. Keep MoQT/WSS topology aligned; distinguish direct WebRTC from TURN/SFU topologies.
- Protocols: MoQT draft-22 over raw QUIC and WSS first; WebRTC DataChannel next. Media paths, MQTT/CoAP and gateway HLS/LL-HLS need separate conditions.
- Synthetic workloads: idle application session; 64 B at 1/10/100 messages/s; 160 B every 20 ms; 16 KiB at 1/5 messages/s. Record instrumentation headers separately. The latter two mimic framing patterns only, not measured audio/JPEG application costs.
- Delivery: bounded queues and an all-data delivery target initially. Count overflow, missing data, corruption and late data. Define deadlines before a live-data series with expiry/drop policies.
- Network: fixed AP, position, channel, power and power-saving settings; record RSSI and retransmissions. Start without injected impairment, then add 50 ms RTT or 1% loss separately at the gateway. These are network impairments, not emulated radio interference.
- Security: encryption and validated server authentication for MoQT/WSS; full handshakes initially, resumption/reuse separately. Record WebRTC peer authentication and signaling trust separately.
- Pilot: six independent blocks per condition, balanced AB/BA for two protocols, seeded randomized order, reset before each independent trial, record startup and 60 seconds of active transfer after readiness. Reconnection is a separate series.
- Main measurement: choose repeat count from pilot variability and a prespecified precision target; consider 10-minute active intervals. Freeze conditions before collection. Longer endurance tests are separate.
- Outputs: success rate with all failures retained, memory peaks and remaining capacity by memory region, CPU, network bytes, startup and delivery timing. Use RTT unless cross-device clock synchronization uncertainty is measured.
- Boundary tests: increase one load variable and bracket observed failure boundaries. Do not infer a linear capacity curve from a few points.
- Controls: radio/network baseline, encrypted transport, application protocol, synthetic traffic, complete application. Separate unsupported platform/draft from allocation and deadline failures. Energy requires suitable instrumentation.

- Investigate MCU-compatible MoQT/QUIC candidates and reproducible WSS/WebRTC builds first.
- Select one ESP32-S3 board/configuration for an initial feasibility pilot if the software investigation supports it; retain Pico-class and smaller application-MCU boards as additional scope candidates.
- Do not require hardware purchase or a VPS at this planning stage. Hardware measurements require an actual selected board; desktop memory caps and emulation are supporting tools only.
- Keep the three previously authorized desktop experiments pending: independent idle connections, active multi-track transfer, and longer steady-state measurements. They support server characterization and do not answer MCU feasibility on their own.
- Publish this investigation, selection decisions, unsuccessful builds and measurements in English. Keep credentials and private network details out of records.

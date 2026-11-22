# Scope revision: fixed resource usage and blog publication

The user requested a return to the original investigation: measure the fixed resource usage of MoQT implementations and use the results to write a blog post.

- Primary series: IETF MoQT draft-22 over raw QUIC on Linux.
- Measure baseline resident memory and idle CPU separately from initial connection/subscription costs and subsequent increments.
- Compare with the same QUIC/TLS stack where a matching control exists. A measured difference also reflects implementation-specific features and settings; it does not isolate pure protocol cost automatically.
- Retain existing experiments, raw observations, failure investigations and reproducibility records.
- Prioritize the three pending measurements: fixed subscriptions with additional idle connections, active multi-track transfer at fixed connection count, and longer steady-state measurement with main-experiment conditions fixed in advance.
- Report Publisher, Relay and Subscriber separately. Fixed client implementations limit conclusions about endpoint implementation differences.
- Defer MCU porting/hardware measurements and cross-technology comparisons. Preserve the IoT investigation as background rather than evidence of resource infeasibility.
- Deliver an English blog post linked to reproducible methods, data and analysis. Do not infer a universal MoQT resource minimum or MCU feasibility from desktop process measurements.
- This change updates the plan only; no new measurements or publication were performed in this revision.

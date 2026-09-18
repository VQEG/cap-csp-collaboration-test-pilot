# FikoRE Co-Simulation Message Reference

This document defines the candidate version 1 JSON wire format for [FikoRE Offline Co-Simulation](fikore-cosim.md).

Protocol evolution:
- Changing field semantics or required schemas increments `protocol_version`.
- Adding optional fields does not increment `protocol_version`.

## Common Rules

- Every message contains a `type` string property.
- Time values represent seconds in simulation time unless the field name ends in `_ms`.
- Byte counts are integers. Bitrates ending in `_mbps` represent Mbit/s.
- Numeric fields must be finite and non-negative unless explicitly specified.
- UE IDs are integer numbers (or decimal string keys when used as JSON object keys).
- Request IDs contain up to 32 characters matching `[A-Za-z0-9_.-]`.
- Parsers ignore unknown fields and reject missing required fields.

## `hello`

FikoRE transmits `hello` immediately upon socket connection.

| Field | Type | Description |
| :-- | :-- | :-- |
| `type` | string | Constant `"hello"` |
| `protocol_version` | integer | Wire version (`1`) |
| `tick_ms` | float | Internal radio simulation tick |
| `sync_ms` | float | Report interval |
| `telemetry_ms` | float | Telemetry aggregation interval |
| `external_ue_ids` | integer array | Active external UE IDs driven by harness |
| `seed` | integer | Emulator seed |
| `duration_s` | float | Scheduled simulation duration |

```json
{"type":"hello","protocol_version":1,"tick_ms":1.0,"sync_ms":10.0,"telemetry_ms":500.0,"external_ue_ids":[0,1,2,3],"seed":17,"duration_s":300.0}
```

## `ready`

The harness responds to `hello` with the negotiated protocol version.

| Field | Type | Description |
| :-- | :-- | :-- |
| `type` | string | Constant `"ready"` |
| `protocol_version` | integer | Negotiated wire version (must match `hello`) |

```json
{"type":"ready","protocol_version":1}
```

## `report`

FikoRE emits sequence 0 at `t = 0.0` s. Subsequent reports summarize progress across each elapsed `sync_ms` window.

| Field | Type | Description |
| :-- | :-- | :-- |
| `type` | string | Constant `"report"` |
| `sequence` | integer | Monotonically increasing sequence number starting at 0 |
| `sim_time_s` | float | Simulation timestamp at end of interval |
| `ue_reports` | object | Per-UE delivery status |
| `telemetry` | object or absent | Per-UE telemetry dictionary (emitted on telemetry boundaries) |

Each entry in `ue_reports` contains:

| Field | Type | Description |
| :-- | :-- | :-- |
| `bytes_delivered` | object | Mapping of active request ID to cumulative delivered bytes |
| `completed` | string array | Request IDs completed during this interval |
| `cancelled` | object | Mapping of cancelled request ID to final cumulative delivered bytes |

Completed requests do not appear in `bytes_delivered`; their delivered byte count equals `bytes_total`.

Telemetry objects contain:

| Field | Type | Description |
| :-- | :-- | :-- |
| `throughput_mbps` | float | Delivered downlink throughput over window |
| `ip_latency_ms` | float | Mean IP one-way delay of delivered packets |
| `pdcp_latency_ms` | float | Mean PDCP delay of delivered packets |
| `ce_rate` | float | Fraction of packets marked congestion experienced |
| `drop_rate` | float | Fraction of radio packets dropped |
| `retransmitted_bytes` | integer | Bytes retransmitted in window |
| `sinr_db` | float | Mean UE SINR |
| `queue_bytes` | integer | Bytes in UE downlink queue at window close |

```json
{"type":"report","sequence":1234,"sim_time_s":12.35,"ue_reports":{"3":{"bytes_delivered":{"v8.s0.q2.a0":184320},"completed":["v7.s2.q1.a0"],"cancelled":{"v7.s3.q1.a0":61440}}},"telemetry":{"3":{"throughput_mbps":8.24,"ip_latency_ms":38.9,"pdcp_latency_ms":41.2,"ce_rate":0.031,"drop_rate":0.004,"retransmitted_bytes":1460,"sinr_db":11.7,"queue_bytes":122880}}}
```

## `commands`

The harness answers every `report` with a matching `commands` message (which may contain an empty array).

| Field | Type | Description |
| :-- | :-- | :-- |
| `type` | string | Constant `"commands"` |
| `sequence` | integer | Sequence number matching the answered report |
| `commands` | object array | List of operations to execute in order |

```json
{"type":"commands","sequence":1234,"commands":[]}
```

## `request` Command

Initiates transfer of an anonymous byte object.

| Field | Type | Description |
| :-- | :-- | :-- |
| `op` | string | Constant `"request"` |
| `ue_id` | integer | Target external UE ID |
| `request_id` | string | Unique request identifier for this UE |
| `bytes_total` | integer | Total object size in bytes |

```json
{"op":"request","ue_id":3,"request_id":"v8.s1.q2.a0","bytes_total":940000}
```

The harness resolves object sizes from its content registry. FikoRE treats `request_id` as an opaque token without parsing video metadata.

## `cancel` Command

Halts generation of new packets for an in-flight object. Cancelling an unknown or completed request is a no-op.

| Field | Type | Description |
| :-- | :-- | :-- |
| `op` | string | Constant `"cancel"` |
| `ue_id` | integer | Target external UE ID |
| `request_id` | string | Active request identifier to cancel |

```json
{"op":"cancel","ue_id":3,"request_id":"v7.s3.q1.a0"}
```

## `control` Command

Proposed L3 command to adjust radio scheduling for a UE.

| Field | Type | Description |
| :-- | :-- | :-- |
| `op` | string | Constant `"control"` |
| `ue_id` | integer | Target external UE ID |
| `priority` | float or absent | Updated scheduler weight |
| `rmax_mbps` | float, null, or absent | Updated rate cap (`null` removes cap; absent leaves unchanged) |

```json
{"op":"control","ue_id":3,"priority":2.0,"rmax_mbps":25.0}
```

## `end`

FikoRE transmits `end` after receiving an empty command response to the final report, or after an abort.

| Field | Type | Description |
| :-- | :-- | :-- |
| `type` | string | Constant `"end"` |
| `sim_time_s` | float | Final simulation timestamp |
| `reason` | string | `"duration_reached"` or `"aborted"` |

## `abort`

The harness transmits `abort` instead of `commands` to terminate simulation early. FikoRE stops and responds with `end`.

| Field | Type | Description |
| :-- | :-- | :-- |
| `type` | string | Constant `"abort"` |
| `reason` | string | Error or cancellation summary |

## `error`

Transmitted when receiving an invalid message. Protocol errors terminate execution immediately.

| Field | Type | Description |
| :-- | :-- | :-- |
| `type` | string | Constant `"error"` |
| `message` | string | Error description |

## Example Protocol Trace

```jsonl
{"type":"hello","protocol_version":1,"tick_ms":1.0,"sync_ms":10.0,"telemetry_ms":500.0,"external_ue_ids":[3],"seed":17,"duration_s":300.0}
{"type":"ready","protocol_version":1}
{"type":"report","sequence":0,"sim_time_s":0.0,"ue_reports":{}}
{"type":"commands","sequence":0,"commands":[{"op":"request","ue_id":3,"request_id":"v0.s0.q2.a0","bytes_total":940000},{"op":"request","ue_id":3,"request_id":"v1.s0.q1.a0","bytes_total":610000}]}
{"type":"report","sequence":1,"sim_time_s":0.01,"ue_reports":{"3":{"bytes_delivered":{"v0.s0.q2.a0":12000,"v1.s0.q1.a0":12000},"completed":[],"cancelled":{}}}}
{"type":"commands","sequence":1,"commands":[]}
```

## Validation Errors

The following conditions trigger immediate protocol errors:

- Version mismatch in `ready`
- Command sequence number not matching the active report
- Duplicate request ID for the same UE
- Command addressing an unconfigured UE ID
- Non-positive `bytes_total`
- Empty `control` payload or negative parameter value
- Non-empty command payload following terminal report
- Socket closed prematurely before `end` exchange

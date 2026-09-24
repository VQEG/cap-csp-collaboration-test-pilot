# FikoRE Co-Simulation Message Reference

This document defines the wire format for [FikoRE Offline Co-Simulation](fikore-cosim.md).

The format is `fikore-control-1`, FikoRE's runtime control protocol. This reference
specifies it to the level both sides can be written against: the framing rules, every
message the pilot uses, the knob catalogue it touches, and the synchronisation loop built
from them.

Protocol evolution: there is no negotiation. The emulator announces a protocol string and
the client must answer with the same string, so a mismatch is a deployment error rather
than a degraded session.

## Common Rules

- Every message is a single-line UTF-8 JSON object terminated by `\n`.
- The canonical instant is `at_tti`, an integer count of 1 ms slots. `at_t`, in seconds,
  is accepted and converted; `at_tti` wins when both are present.
- Units are part of the field or knob name, and they are the units of the `.ini` file,
  not the emulator's internal ones.
- Directional knobs carry a mandatory `dl.` or `ul.` prefix. There is no unprefixed form.
- Byte counts are integers. Rates ending in `_mbps` are Mbit/s.
- UE IDs are integers, addressed as the target string `ue/<id>`.
- A message is validated whole before anything is applied, so a `ue/*` carrying one bad
  value never leaves half the UEs updated.
- There is no deduplication by `id` and there are no incremental operators. A correct
  client is assumed.
- The channel is bidirectional and asymmetric: the harness sends commands, the emulator
  sends the greeting, one `ack` per command message, and errors. Every example below is
  labelled with its direction, and no code block mixes the two.

## `hello`

FikoRE transmits `hello` immediately upon socket connection. The harness answers with the
same protocol string or the connection is closed.

Emulator → harness, on connection:

```json
{"op":"hello","proto":"fikore-control-1"}
```

Harness → emulator, in reply:

```json
{"proto":"fikore-control-1"}
```

Only one client is served at a time. A second connection receives
`{"op":"error","reason":"control channel already in use"}` and is closed.

Run-level metadata that the spec's `hello` carried is read instead with `get cell`
(see [`get`](#get)), which returns the tick, the scheduled duration, the scheduler type
and the cell's radio configuration.

## Command Envelope

The harness sends commands; the emulator answers each message with one [`ack`](#ack).

| Field | Type | Description |
| :-- | :-- | :-- |
| `id` | integer | Correlation identifier, echoed in the `ack` |
| `at_tti` | integer, optional | TTI at which to apply. Absent means "on the next tick" |
| `at_t` | float, optional | Same instant in seconds; `at_tti` wins if both are present |
| `cmds` | object array | Commands, applied in order at that instant |

Each command carries `op` (defaulting to `"set"`) and `target`, one of `ue/<id>`,
`ue/*` or `cell`.

Harness → emulator:

```json
{"id":42,"at_tti":5000,"cmds":[{"target":"ue/3","set":{"priority":4.0,"dl.rmax_mbps":25.0}}]}
```

## `set`

Writes knobs from the catalogue. `describe` returns the authoritative catalogue at
runtime; the knobs this pilot uses are:

| Knob | Unit | Meaning |
| :-- | :-- | :-- |
| `priority` | — | Scheduling priority. **Absolute**: replaces the `.ini` value, it does not multiply it. Ignored by the round-robin scheduler |
| `dl.rmax_mbps` | Mbps | Rate cap over the air. `0` removes the cap |
| `dl.inject_bytes` | bytes | Hands N bytes to the UE now. **Incremental**; its read returns the cumulative total |
| `pkt_delay_budget_s` | s | PDCP delay budget, `0.001`–`60`. See [delivery](fikore-cosim.md#delivery-guarantees) |
| `enabled` | bool | Attaches or detaches the UE |

Uplink equivalents carry the `ul.` prefix. Mobility, SINR offset and background traffic
rate are also in the catalogue and are not used by this pilot.

## `inject`

Injection of bytes belonging to one object. The `tag` is an opaque integer that the
emulator attaches to the generated packets and uses to attribute delivery.

| Field | Type | Description |
| :-- | :-- | :-- |
| `op` | string | Constant `"inject"` |
| `target` | string | `ue/<id>` |
| `tag` | integer | Object tag, `1`–`2^32-1`. `0` is reserved for generator traffic |
| `dl.bytes` | integer | Bytes to hand over now |

Harness → emulator:

```json
{"id":43,"cmds":[{"op":"inject","target":"ue/3","tag":7,"dl.bytes":12000}]}
```

The harness owns the mapping from its own `request_id` (`v8.s1.q2.a0`) to the integer
tag. FikoRE never sees the request identifier, and stores four bytes per packet rather
than a string.

Untagged injection through `set` is equivalent to `tag: 0`.

## `forget`

Releases a tag's counters. The emulator cannot know when an object is finished — it does
not know `bytes_total` — so the harness, which does, says when it may forget.

| Field | Type | Description |
| :-- | :-- | :-- |
| `op` | string | Constant `"forget"` |
| `target` | string | `ue/<id>` |
| `tag` | integer | Tag to release. Unknown tags are a no-op |

## `get`

Reads knob values plus a `state` block. `ue/*` returns every UE in one reply, which is
what makes one round trip per synchronisation window enough.

Harness → emulator:

```json
{"id":44,"at_tti":5009,"cmds":[{"op":"get","target":"ue/*"}]}
```

Each entry of the result carries every readable knob, plus `state.dl` and `state.ul`:

| Field | Unit | Description |
| :-- | :-- | :-- |
| `injected_bytes_total` | bytes | What the emulator says it received |
| `delivered_bytes_total` | bytes | What reached the far end, after air and backhaul |
| `expired_bytes_total` | bytes | Sat longer than `pkt_delay_budget_s`. Deterministic, and about that packet's own age |
| `dropped_bytes_total` | bytes | Every other loss. The sum of the two below |
| `queue_dropped_bytes_total` | bytes | The AQM asked the sender to slow down, a full buffer tail-dropped, or the UE was detached |
| `radio_dropped_bytes_total` | bytes | HARQ retransmissions exhausted. The only loss that means the link is bad |
| `ce_packets_total` | packets | Marked congestion-experienced |
| `pending_bytes`, `pending_packets` | bytes, packets | Still queued |
| `oldest_age_s` | s | Age of the oldest queued packet; margin against the budget |
| `latency_s` | s | Recent mean **one-way** IP latency |
| `sinr_db` | dB | Mean SINR over the recent window |
| `retransmitted_bytes_total` | bytes | Bytes that went over the air more than once. Reads zero while the radio carries no HARQ error model; see [who retransmits](fikore-cosim.md#who-retransmits) |
| `objects` | — | Per-tag counters, see below |

All counters are cumulative and monotonic, so the harness differences two reads and a
lost read costs nothing. They are resolved when the `get` is applied, at the start of
that TTI's simulation step, and stamped in simulation time.

`objects` maps each live tag to the same three terminal counters. Emulator → harness, as
a fragment of the `ack` result:

```json
{"objects":{"7":{"delivered_bytes":184320,"dropped_bytes":0,"expired_bytes":1500,"queue_dropped_bytes":0,"radio_dropped_bytes":0}}}
```

`get cell` returns the run's metadata: `scenario_type`, `frequency_hz`, `bandwidth_hz`,
`numerology`, `n_freq_rbg`, `metric_type`, `period_ms`, `duration_s`, `map_file`,
`realtime`, `n_ues`, `n_ues_enabled` and `apothem_m`.

## `grant`

Advances the barrier. The emulator runs TTI `n` only while `n <= credit_until_tti`.

| Field | Type | Description |
| :-- | :-- | :-- |
| `op` | string | Constant `"grant"` |
| `until_tti` | integer | Last TTI the emulator may execute |

Harness → emulator:

```json
{"id":45,"op":"grant","until_tti":1500}
```

Credit is absolute and monotonic. Granting into the past is a no-op answered with `ok`
and the credit in force, which is what a client retrying after a timeout needs. The
initial credit is `-1`, so with `sync_mode: barrier` the emulator stops before TTI 0 and
the harness can submit its first requests before time advances.

A `grant` takes effect as soon as it is accepted, not at a scheduled instant: it is what
releases the barrier, so it cannot wait for simulated time to advance.

## `describe` and `ping`

`describe` returns the knob catalogue — name, type, unit, range and description — which
is the authoritative contract at runtime. `ping` returns the current TTI and simulation
time.

## `ack`

The emulator answers every command message.

| Field | Type | Description |
| :-- | :-- | :-- |
| `id` | integer | Echoed from the command |
| `status` | string | `"ok"` or `"error"` |
| `tti` | integer | TTI at which it was applied |
| `t` | float | Simulation time at which it was applied |
| `errors` | array, optional | `{"key", "reason"}` per rejected value |
| `credit_until_tti` | integer, optional | Credit in force after a `grant` |
| `result` | object, optional | Payload of `get` or `describe` |

Emulator → harness:

```json
{"id":42,"status":"ok","tti":5000,"t":5.0}
```

The `ack` states the exact instant of application, so the harness never has to infer when
a command took effect.

## `error`

Sent when a line cannot be parsed or the protocol is violated. Emulator → harness,
unsolicited and without an `id`:

```json
{"op":"error","reason":"control channel already in use"}
```

## Synchronisation Loop

One window of `sync_ms` costs two lines out and two lines back. The `get` is scheduled on
the **last TTI of the window** so that its reply arrives while the emulator still holds
credit, which is what lets the harness read state and grant the next window without
deadlocking.

Emulator → harness, on connection:

```json
{"op":"hello","proto":"fikore-control-1"}
```

Harness → emulator, the reply and then the whole window, written without reading in
between:

```jsonl
{"proto":"fikore-control-1"}
{"id":1,"cmds":[{"op":"inject","target":"ue/3","tag":7,"dl.bytes":12000},{"op":"get","target":"ue/*"}],"at_tti":9}
{"id":2,"op":"grant","until_tti":9}
```

Emulator → harness, one `ack` per command message, in either order:

```jsonl
{"id":1,"status":"ok","tti":9,"t":0.009,"result":[{"target":"ue/3","priority":4.0,"state":{"dl":{"delivered_bytes_total":8192,"objects":{"7":{"delivered_bytes":8192,"dropped_bytes":0,"expired_bytes":0}}}}}]}
{"id":2,"status":"ok","tti":9,"t":0.009,"credit_until_tti":9}
```

The reply reports the state after TTI 8, one slot before the window closes. Over a 10 ms
window that is a 1 ms lag in the observation, which the harness records and the policy
ignores.

Two rules the adapter has to get right, both consequences of when a command is applied
and when it is acknowledged:

- **Do not wait for the acknowledgement of a scheduled command before granting the credit
  that applies it.** A command carrying `at_tti` is applied when the emulator reaches that
  TTI, and in barrier mode it gets there only on credit. Write the commands, write the
  `grant`, then read. Blocking on the first acknowledgement deadlocks the run until
  `credit_timeout_ms` expires.
- **Match acknowledgements by `id`, not by order.** A `grant` is acknowledged as soon as
  it is accepted, while every other command is acknowledged when it is applied, so
  replies do not necessarily come back in the order they were sent.

If measurement shows the two round trips per window dominate run time, the alternative is
a report pushed by the emulator at the barrier, carrying the same `state` payload without
being asked. That is an optimisation, not a prerequisite, and it is deferred until the
harness is running.

## Validation Errors

The following conditions are rejected:

- Protocol string mismatch in the reply to `hello`
- A second simultaneous connection
- Unknown target, unknown knob, or a value out of range
- `set` with no values, or a command with no target
- `grant` without `until_tti`
- Non-positive injection sizes

Whether a protocol error ends the run is governed by `on_timeout` and `on_peer_loss`; see
[termination](fikore-cosim.md#termination-and-error-handling).

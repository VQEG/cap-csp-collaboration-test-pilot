# FikoRE Co-Simulation Message Reference

This document summarizes the `fikore-control-1` operations used by [offline co-simulation](fikore-cosim.md). The implementation in the pinned submodule is authoritative.

## Framing and Handshake

Messages are single-line UTF-8 JSON terminated by `\n`. FikoRE creates the Unix stream socket and sends:

```json
{"op":"hello","proto":"fikore-control-1"}
```

The client replies:

```json
{"proto":"fikore-control-1"}
```

There is no version negotiation and only one client may own the control connection.

## Command Envelopes

Scheduled commands use:

```json
{
  "id":42,
  "at_tti":5000,
  "cmds":[
    {"target":"ue/3","set":{"priority":4.0}},
    {"op":"events","after":123,"include_state":false}
  ]
}
```

`at_tti` is an absolute integer 1 ms slot. An absent instant means the next quiescent point. The complete envelope is validated before any command mutates state.

An envelope containing N commands receives N acknowledgements. Every reply echoes the envelope `id`; replies belonging to that ID remain in command order. A grant has its own ID and its acknowledgement may interleave because the socket thread accepts credit before scheduled work is applied.

## UE Identity

Numeric scheduler targets remain valid:

```text
ue/0
```

The stable textual `ue_id` from configuration is also valid:

```text
ue/car
ue/car_0
ue/car_1
```

Replies retain numeric `target` and add `ue_id` when available.

## `set`

`set` changes runtime UE parameters such as priority, directional rate cap, SINR offset, position, speed, background rate, delay budget and attach state. Directional knobs carry `dl.` or `ul.` prefixes.

```json
{"id":1,"cmds":[{"target":"ue/0","set":{"priority":4.0,"dl.rmax_mbps":25.0}}]}
```

The runtime `describe` operation is the authoritative knob catalogue.

## `inject`

`inject` hands bytes with an opaque 32-bit tag to one UE:

```json
{"id":2,"cmds":[
  {"op":"inject","target":"ue/0","tag":8817,"dl.bytes":1500,"ecn":"not-ect"}
]}
```

The tag identifies one submitted transport segment, not an application object. The player request ID remains above the wire boundary. Accepted ECN values are `not-ect`, `ect0`, `ect1`/`l4s` and `ce`.

## `events`

Transport clients use additive retained event deltas:

```json
{"id":3,"cmds":[{"op":"events","after":123,"include_state":false}]}
```

Example acknowledgement:

```json
{
  "id":3,
  "status":"ok",
  "tti":940,
  "result":{
    "cursor":125,
    "events":[
      {
        "seq":124,
        "at_tti":939,
        "target":"ue/0",
        "ue_id":"car",
        "dir":"dl",
        "tag":8817,
        "delivered_bytes":1500,
        "ce_bytes":1500
      },
      {
        "seq":125,
        "at_tti":939,
        "target":"ue/1",
        "dir":"dl",
        "tag":730,
        "expired_bytes":1500
      }
    ]
  }
}
```

Zero deltas are omitted. Wire fields are `delivered_bytes`, `expired_bytes`, `queue_dropped_bytes`, `radio_dropped_bytes` and `ce_bytes`.

`after` confirms consumption through that cursor. Retrying the same cursor replays unacknowledged logical events. The client advances only after validating the whole response.

`include_state: true` adds compact cumulative telemetry without the knob catalogue or live-object map. It includes queue, latency, SINR, counters and mobility.

## Retention and Resynchronisation

`max_object_events` defaults to 65536:

- barrier overflow aborts before feedback is lost;
- asynchronous overflow reports a gap;
- an asynchronous client recovers atomically with:

```json
{"id":4,"cmds":[{"op":"events","after":0,"resync":true}]}
```

The response includes a complete snapshot, clears the gap and restarts delta collection at the same quiescent point.

## `forget`

`forget` releases terminal tag counters:

```json
{"id":5,"cmds":[{"op":"forget","target":"ue/0","tag":8817}]}
```

An unacknowledged retained event is not removed. The correct order is: observe terminal outcome, acknowledge its cursor, then forget.

## `grant`

`grant` gives absolute barrier credit:

```json
{"id":6,"op":"grant","until_tti":940}
```

Credit is monotonic. The client must send scheduled commands and the grant before waiting for replies; otherwise a command scheduled in the future cannot be applied and both sides deadlock.

## `get`, `describe` and `ping`

- `get` returns a complete stateless diagnostic view.
- `describe` returns the runtime knob catalogue.
- `ping` returns current TTI and simulation time.

The per-TTI transport path uses `events`; polling `get ue/*` with a growing live object map is not the scalable feedback path.

## Lockstep Exchange

For every internal TTI, `FikoreLink`:

1. writes due `inject`, `forget`, control and `events` commands;
2. writes the absolute `grant`;
3. reads the expected acknowledgement count for every ID;
4. validates event sequence and cursor;
5. converts terminal tag outcomes into segment arrivals.

Counter movements occurring in TTI `n` are collected at the quiescent point of TTI `n+1`; transports react only when feedback is observable.

See [`runtime-control-events.md`](../5g-network-emulator/docs/runtime-control-events.md) for the emulator-side cursor contract.

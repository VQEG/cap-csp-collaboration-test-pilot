# PR body draft — collaboration wiring (`cap-csp-collaboration-test-pilot`)

**GitHub PR description only** — paste into GitHub when opening the pilot PR. Normative field rules stay in [`collaboration.md`](collaboration.md) and [`signaling.md`](signaling.md); this text is for **Michi**, **Werner**, and other reviewers who need the change story in one place.

**Proposed merge:** `feature/shared-state-table-v1` → `master` on [VQEG/cap-csp-collaboration-test-pilot](https://github.com/VQEG/cap-csp-collaboration-test-pilot).

**Blocked on:** merge [micseu/SFV-Reference-Implementation](https://github.com/micseu/SFV-Reference-Implementation) `feature/vqeg-collaboration-hooks` first (engine hooks required even at L0).

---

## Summary

This pull request adds the **VQEG collaboration bus** to the pilot harness: CSP telemetry and CAP reports go through one **in-process shared state table** (`capcsp/shared_state`), with an append-only **`shared-state.jsonl`** audit on every run. On each simulation step, Python maps backend telemetry into the table, attaches a signaling-filtered **`collaboration`** object to the player IPC `network_step`, collects **`cap_reports`** from Node, and—at L3+ with `csp_controller: "dummy"`—logs control proposals to **`csp-control.jsonl`** without calling `set_ue_control`.

**FikoRE submodule:** `master` already tracks `5g-network-emulator` `origin/dev` at `13f9b83` (via `97098fa`); this PR does not introduce a new emulator bump beyond collaboration wiring.

**B1/B2 scoring and SFV policy are unchanged.** Rules do not consume `getCspFields()` yet.

**Out of this repository:** SFV engine hooks (`applyCspUpdate`, `buildCapReport`) are delivered in a **separate** [SFV-Reference-Implementation](https://github.com/micseu/SFV-Reference-Implementation) pull request. This pilot PR only defines the IPC contract and calls those methods from `capcsp/player/js/network_step_harness.js`. Companion SFV reviewer text: [`pr-body-draft-sfv-collaboration-hooks.md`](pr-body-draft-sfv-collaboration-hooks.md) in this repo’s `docs/`.

---

## Why integrate in this order

| Step | Repository | What happens |
|------|------------|--------------|
| **1 — this PR** | `cap-csp-collaboration-test-pilot` | Shared table, Python tick, thin Node harness, docs, tests, FikoRE submodule at `dev`. |
| **2 — follow-up** | `micseu/SFV-Reference-Implementation` | Engine hooks + unit tests (SFV PR body in this repo’s `docs/`). |
| **3 — follow-up** | `cap-csp-collaboration-test-pilot` | Bump `sfv-reference-implementation` submodule to the merged SFV commit; CI then matches production layout. |

Until step 3, a checkout with the **published** SFV submodule tag (`v0.7.0`) fails at runtime with an explicit error if `buildCapReport` is missing—there is no silent fallback. Development on this branch uses a **local submodule commit** that carries the hook patches for integration testing only; that submodule delta is **not** part of step 1’s merge intent.

---

## What this PR contains

### Python

| Area | Role |
|------|------|
| `capcsp/shared_state/` | Table, `CspFields` / `CapReport`, telemetry → fields mapping, signaling read filters |
| `capcsp/collaboration/` | Per-step tick (`run_collaboration_tick`, `apply_player_network_events`), telemetry ingest, CAP reporter, `DummyCSPController`, FikoRE / no-op control adapters, `CollaborationContext` factory |
| `capcsp/runner/run.py` | Always wires collaboration; manifest fields `shared_state_log`, `csp_control_log`, `clock_mode`, `cap_application` |
| `capcsp/player/bridge.py` | Requires `CollaborationContext`; ordered tick documented in [`collaboration.md`](collaboration.md) |

### Node (pilot repo only)

- `network_step_harness.js`: applies `step.collaboration` via `applyCspUpdate`; `cap_reports` via `buildCapReport` on the SFV controller (no table access in Node).
- Player-facing steps **omit** raw `NetworkTelemetryReceived` (telemetry stays in `telemetry.jsonl` and the table).

### FikoRE / emulator submodule

- Pointer: `5g-network-emulator` @ **`13f9b83`** on branch **`dev`** (`https://github.com/nokia/5g-network-emulator`).
- Pilot code: `FikoreControlAdapter` maps `CspControlIntent` → `set_ue_control`; **`DummyCSPController` never calls `apply`**. No new CSP algorithms in this PR.

### Artifacts (all signaling levels)

| File | When |
|------|------|
| `shared-state.jsonl` | Every run |
| `csp-control.jsonl` | L3+ and `csp_controller: "dummy"` |
| `network-steps.jsonl` | Includes `collaboration`; no raw telemetry events |
| `telemetry.jsonl` | Unchanged flat backend log (not the collaboration bus) |

Example L3 config: [`configs/experiments/collaboration/l3-dummy-mock.json`](../configs/experiments/collaboration/l3-dummy-mock.json).

### Tests and docs

- `tests/test_collaboration.py`, `tests/test_shared_state.py`, extensions in `tests/test_runs.py` (62 tests on this branch).
- Updated: `collaboration.md`, `signaling.md`, `architecture.md`, and cross-links.

---

## Tick order (implementation)

After each `NetworkBackend.advance()`:

1. Validate byte-path events; ingest `NetworkTelemetryReceived` → table (+ `telemetry.jsonl`).
2. Build `collaboration` from `read_csp_fields` (signaling filter).
3. IPC `network_step` to Node; SFV step logic (B1/B2 unchanged).
4. `cap_reports` IPC → `write_cap_report` per UE.
5. If L3+ dummy controller: log proposals (`applied: false`).
6. If not final: apply player submit/cancel to the backend.

Steps 2–5 run inside `run_collaboration_tick`; step 6 runs in `bridge.run_sessions` before the next advance.

---

## Compatibility

- **L0 (default):** Table still records writes; `collaboration.csp_by_ue` is empty for the player. KPI hashes stable (`test_l0_determinism_hash_stable`).
- **L3 dummy:** Full bidirectional **logging**; no effective scheduler control.

Deliberately **not** in this PR: B1/B2 policy on CSP fields, real `CSPController` calling `apply`, L4 oracles, live wall-clock runtime, merging SFV hooks into `micseu` main.

Further work: [`implementation-plan.md`](implementation-plan.md), [`decision-status-and-todos.md`](decision-status-and-todos.md).

---

## Test plan

Verified on `feature/shared-state-table-v1` before opening the PR (Node.js required for integration tests).

- [x] `uv run pytest -q` — **66 passed** (~12 s)
- [x] Collaboration wiring: `tests/test_collaboration.py`, `tests/test_shared_state.py`; E2E in `tests/test_runs.py` (`test_mock` collaboration IPC, `test_l3_dummy_writes_csp_control`, `test_l0_determinism_hash_stable`, `test_run_writes_p1203_scores` → `shared-state.jsonl`)
- [x] L3 smoke: `uv run capcsp run configs/experiments/collaboration/l3-dummy-mock.json /tmp/capcsp-l3-smoke` — run **completed**; `shared-state.jsonl` and `csp-control.jsonl` present; manifest `csp_control_log` / `shared_state_log` set
- [x] L0 hash stability: `test_l0_determinism_hash_stable` (mock B1/B2, separate processes / `PYTHONHASHSEED`); FikoRE when built — `test_fikore_run_repeats_with_a_different_python_hash_seed` (skips if `TransportFikoreConfig().fikore_binary` missing)
- [x] Doc consistency: `docs/collaboration.md` vs `capcsp/collaboration/runtime.py` and `capcsp/player/bridge.py` (tick order)

---

## Remote / branch checklist (for whoever opens the PR)

| Remote | Default branch | This work |
|--------|----------------|-----------|
| `origin` → `git@github.com:VQEG/cap-csp-collaboration-test-pilot.git` | `master` | PR **from** `feature/shared-state-table-v1` |
| Submodule `5g-network-emulator` | `dev` @ `13f9b83` | Already aligned with `origin/dev` after `git submodule update --remote` |
| Submodule `sfv-reference-implementation` | `main` @ `07fab25` | **Do not** rely on a submodule bump in **this** merge; step 3 above |

After `git fetch origin`, `master` is the merge base; other remote branches (`feat/sfv-player-integration`, `js-player-and-transport-models`) are unrelated to this PR.

---

## Suggested reviewer focus

1. Does the **single-table** model match [`signaling.md`](signaling.md) L0–L3 read/write rules?
2. Is the **IPC boundary** (`collaboration` in, `cap_reports` out) enough for the SFV follow-up without Node touching the table?
3. Is the **FikoRE submodule bump** acceptable for current VQEG condition configs (see commit `97098fa` message for C5 metric deltas)?

Treat as **infrastructure for signaling experiments**: L0 scores should stay comparable; use L3 dummy configs to audit the bus before policy or effective control land in later PRs.

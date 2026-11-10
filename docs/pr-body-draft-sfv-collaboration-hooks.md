# PR body draft — SFV collaboration hooks (`SFV-Reference-Implementation`)

**GitHub PR description only** — paste into GitHub when opening the **player engine** PR on [micseu/SFV-Reference-Implementation](https://github.com/micseu/SFV-Reference-Implementation).

Field semantics and signaling levels are defined in the pilot: [signaling.md](https://github.com/VQEG/cap-csp-collaboration-test-pilot/blob/master/docs/signaling.md) and [player-api.md](https://github.com/VQEG/cap-csp-collaboration-test-pilot/blob/master/docs/player-api.md). This repository change adds **engine APIs only**—no Python table, no FikoRE wire format.

**Proposed merge:** feature branch (e.g. `feature/vqeg-collaboration-hooks`) → `main`.

**Companion (pilot repo, merges first):** [collaboration wiring PR body](https://github.com/VQEG/cap-csp-collaboration-test-pilot/blob/master/docs/pr-body-draft-collaboration-wiring.md) on [VQEG/cap-csp-collaboration-test-pilot](https://github.com/VQEG/cap-csp-collaboration-test-pilot).

---

## Summary

This pull request adds **VQEG collaboration hooks** to the SFV reference implementation so offline co-simulation and the browser player share the same CAP-facing surface:

- **CSP → CAP:** `applyCspUpdate(fields, time_s)` stores a normalized CSP snapshot and emits `CSP_TELEMETRY_UPDATED` with **`triggerDecision: false`**.
- **CAP → CSP:** `buildCapReport(time_s)` returns the pilot `cap_reports` payload (`time_s`, `is_stalled`, `playable_buffer_s`, `current_video_id`, `swipe_rate_per_s`).

The VQEG **NetworkStep harness** in the pilot repo calls these methods each co-simulation step. The harness does not implement CAP/CSP policy; it forwards `step.collaboration` and answers `cap_reports`. See [collaboration.md](https://github.com/VQEG/cap-csp-collaboration-test-pilot/blob/master/docs/collaboration.md).

**Behaviour change for existing scenarios:** none at L0. B1/B2 still use download-history EWMA; `getCspFields()` is available but unused until a later policy PR.

---

## Integration order (with the pilot)

| Step | Where | Action |
|------|--------|--------|
| 1 | `cap-csp-collaboration-test-pilot` | Merge **collaboration wiring** (table, Python tick, harness IPC, FikoRE submodule). Submodule pointer for SFV may still be `v0.7.0` on `main`. |
| 2 | **This PR** | Merge hooks into `SFV-Reference-Implementation` `main`. |
| 3 | `cap-csp-collaboration-test-pilot` | Small PR: bump `sfv-reference-implementation` submodule to the merged commit; `uv run pytest -q` on the pilot. |

Reviewers can read steps 1 and 2 in parallel. Production-like pilot runs need step 3; step 1’s harness already documents the IPC contract step 2 implements.

---

## Motivation

The pilot centralizes CAP–CSP state in a Python **shared table** and exposes filtered views on IPC. Previously, CAP reports were assembled in the legacy [SFV-VQEG harness](https://github.com/micseu/SFV-VQEG-CAP-CSP-Collaboration-Experiments) by scraping playback state, and CSP snapshots never entered the SFV engine.

Hooks in SFV core give:

1. One implementation for `SFVSimulationController` and `SFVBrowserController`.
2. A stable surface for the pilot harness and for a future **live** adapter (same JSON as `collaboration.csp_by_ue`).
3. A path to align rules with `Observation.csp_fields` without a second telemetry bus in Node.

The player **never** reads the shared table.

---

## What changes

### New modules (`src/core/`)

| Module | Role |
|--------|------|
| `SFVCspFields.js` | `normalizeCspFields`, `cspFieldsEqual` — pilot `CspFields` keys |
| `SFVCapReport.js` | `buildCapReportFromSession` — pilot `cap_reports` shape |

### Controllers

| Class | New API |
|-------|---------|
| `SFVSimulationController` | `applyCspUpdate`, `getCspFields`, `buildCapReport` |
| `SFVBrowserController` | same |

### Rules context

- `SFVRulesContext.getCspFields()` returns the latest snapshot or `null`.

### CAP reports (co-sim)

- One snapshot per harness call (per network step), matching legacy SFV-VQEG `getCapReports` timing.
- Stall/buffer **transition** reporting with ≤1 Hz cap per [signaling.md](https://github.com/VQEG/cap-csp-collaboration-test-pilot/blob/master/docs/signaling.md) — **future** PR.

---

## Pilot harness (after submodule bump)

In [network_step_harness.js](https://github.com/VQEG/cap-csp-collaboration-test-pilot/blob/master/capcsp/player/js/network_step_harness.js):

- Each `network_step`: `applyCspUpdate(csp_by_ue[ue], time_s)` when present.
- `cap_reports` IPC: `buildCapReport(time_s)` per started UE.

Python: `SfVCapReporter` → `write_cap_report` (unchanged once step 3 lands).

---

## Out of scope (this PR)

- B1/B2 logic that reads `getCspFields()` or sets `triggerDecision: true` on `CSP_TELEMETRY_UPDATED`.
- L4 `oracle_capacity_trace`, live HTTP adapter, dash.js catalogue work.
- FikoRE, Python shared table, or `5g-network-emulator` changes.

---

## Test plan

Verified on the feature branch (hooks in `src/core/`, controllers, and tests below) before opening the PR.

- [x] Collaboration hooks: `node --test test/csp-fields.test.js test/cap-report.test.js` — **4 passed**
- [x] Full SFV suite: `npm test` — **170 passed** (~6.5 s); existing B1/B2 and scenario tests unchanged aside from the new modules
- [x] Pilot integration (local submodule / branch checkout, not step 3 pointer yet): `uv run pytest -q` in [cap-csp-collaboration-test-pilot](https://github.com/VQEG/cap-csp-collaboration-test-pilot) — **62 passed** with these hooks wired through `network_step_harness.js`

Release gate for micseu remains `npm run verify` if the repository requires it; this PR was checked with `npm test` only.

---

## Remote / branch checklist

| Remote | Default branch | Notes |
|--------|------------------|--------|
| `origin` → `git@github.com:micseu/SFV-Reference-Implementation.git` | `main` | Push feature branch here; open PR to `main` |
| Pilot submodule | Currently `07fab25` (`v0.7.0`) on pilot `master` | Bump only in pilot step 3 |

Local development in the pilot often points the submodule at a path clone with these commits; that layout is for integration testing, not for mixing SFV file changes into the pilot wiring PR.

---

## Suggested merge note

Safe to merge as **plumbing only**: existing SFV validation and browser runs should match prior behaviour; pilot L0 determinism hashes should remain stable once the pilot submodule pointer is updated (step 3).

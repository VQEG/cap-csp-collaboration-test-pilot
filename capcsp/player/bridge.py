"""Bridge between a network backend and the Node.js SFV player process.

Adapted from scripts/generic_player_bridge.py in SFV-VQEG-CAP-CSP-Collaboration-Experiments
v0.7.2 by Michael Seufert:
https://github.com/micseu/SFV-VQEG-CAP-CSP-Collaboration-Experiments/blob/9d7d6f9/scripts/generic_player_bridge.py

One Node.js process runs the sessions of all UEs. For each backend step, Python
validates the byte events, polls the backend's CSP telemetry into the shared
state table, attaches the filtered ``collaboration`` snapshot and sends the step
over IPC; after CAP reports (and optional CSPController) it applies returned
submissions and cancellations to the backend. Network telemetry never reaches
the player except through that snapshot.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Callable

from capcsp.collaboration.factory import CollaborationContext
from capcsp.collaboration.runtime import (
    apply_player_actions,
    apply_player_network_events,
    run_collaboration_tick,
)
from capcsp.network.api import NetworkBackend, step_to_dict

REPO_ROOT = Path(__file__).resolve().parents[2]
# The co-simulation adapter lives in SFV; the JSON lines protocol is the only interface.
WORKER = REPO_ROOT / "sfv-reference-implementation" / "scripts" / "cosim-network-step-worker.mjs"


class NodePlayerBridge:
    """Line-delimited JSON exchange with the player process."""

    def __init__(self, config: dict[str, Any], *, log_path: Path, executable: str = "node") -> None:
        # stderr goes to a file so that a full pipe cannot block the player process
        self._log = open(log_path, "w", encoding="utf-8")
        self.process = subprocess.Popen(
            [executable, str(WORKER)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self._log,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        response = self.exchange({"type": "initialize", "config": config})
        if response != {"type": "initialized"}:
            raise RuntimeError(f"Player initialization failed: {response}")

    def exchange(self, message: dict[str, Any]) -> dict[str, Any]:
        if self.process.poll() is not None or not self.process.stdin or not self.process.stdout:
            raise RuntimeError(f"Player process exited with code {self.process.returncode}")
        self.process.stdin.write(json.dumps(message, allow_nan=False) + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError("Player process closed its output")
        response = json.loads(line)
        if response.get("type") == "error":
            raise RuntimeError(f"Player error: {response.get('message')}")
        return response

    def on_step(self, step_dict: dict[str, Any]) -> dict[str, Any]:
        return self.exchange({"type": "network_step", "step": step_dict})

    def close(self) -> None:
        if self.process.poll() is None:
            if self.process.stdin:
                self.process.stdin.close()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        if self.process.stdout:
            self.process.stdout.close()
        self._log.close()

    def __enter__(self) -> NodePlayerBridge:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def run_sessions(
    backend: NetworkBackend,
    bridge: NodePlayerBridge,
    *,
    ue_ids: set[int],
    transcript: list[dict[str, Any]],
    telemetry: list[dict[str, Any]],
    collaboration: CollaborationContext,
    max_steps: int = 1_000_000,
    on_step: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    """Run all sessions on the backend clock until the final step.

    Checks every event against the requests the player submitted, and returns
    the player's final result. `on_step` receives the simulated time of every step.
    """
    previous_time = -1.0
    sizes: dict[tuple[int, str], int] = {}
    delivered: dict[tuple[int, str], int] = {}
    terminal: set[tuple[int, str]] = set()
    for _ in range(max_steps):
        step = backend.advance()
        if step.time_s <= previous_time:
            raise ValueError(f"Backend time did not advance: {step.time_s} after {previous_time}")
        previous_time = step.time_s
        if on_step is not None:
            on_step(step.time_s)
        step_dict = step_to_dict(step)
        apply_player_network_events(
            step_dict,
            ue_ids=ue_ids,
            sizes=sizes,
            delivered=delivered,
            terminal=terminal,
        )
        telemetry.extend(collaboration.telemetry.poll_and_write(force=step.is_final))
        response, logged_step = run_collaboration_tick(
            step_dict,
            bridge=bridge,
            collaboration=collaboration,
            ue_ids=ue_ids,
        )
        transcript.append({"network_step": logged_step, "player_response": response})
        if step.is_final:
            if response.get("type") != "player_step_result" or response.get("actions"):
                raise ValueError("Expected a final player result without actions")
            return response["result"]
        apply_player_actions(backend, response, ue_ids=ue_ids, sizes=sizes, delivered=delivered)
    raise RuntimeError(f"Run exceeded {max_steps} steps")

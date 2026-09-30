"""Bridge between a network backend and the Node.js SFV player process.

Adapted from scripts/generic_player_bridge.py in SFV-VQEG-CAP-CSP-Collaboration-Experiments
v0.7.2 by Michael Seufert:
https://github.com/micseu/SFV-VQEG-CAP-CSP-Collaboration-Experiments/blob/9d7d6f9/scripts/generic_player_bridge.py

One Node.js process runs the sessions of all UEs. For each backend step, the
bridge sends the whole NetworkStep, then applies the returned submissions and
cancellations to the backend. The player never sees backend-specific messages.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from capcsp.network.api import NetworkBackend, step_to_dict

WORKER = Path(__file__).resolve().parent / "js" / "worker.mjs"


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
    max_steps: int = 1_000_000,
) -> dict[str, Any]:
    """Run all sessions on the backend clock until the final step.

    Checks every event against the requests the player submitted, and returns
    the player's final result.
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
        step_dict = step_to_dict(step)
        for event in step_dict["events"]:
            if event["ue_id"] not in ue_ids:
                raise ValueError(f"Event for unknown UE {event['ue_id']}")
            if event["event_type"] == "NetworkTelemetryReceived":
                telemetry.append({"ue_id": event["ue_id"], "time_s": event["time_s"], **event["fields"]})
                continue
            key = (event["ue_id"], event["request_id"])
            if key not in sizes or key in terminal:
                raise ValueError(f"Event for unknown or finished request {key}")
            if "bytes_delivered" in event:
                if not delivered[key] <= event["bytes_delivered"] <= sizes[key]:
                    raise ValueError(f"Invalid cumulative byte count for {key}")
                delivered[key] = event["bytes_delivered"]
            if event["event_type"] == "DownloadCompleted":
                # Completion implies all bytes arrived, even without a final progress event
                delivered[key] = sizes[key]
                terminal.add(key)
            elif event["event_type"] == "DownloadCancelled":
                terminal.add(key)
        response = bridge.on_step(step_dict)
        transcript.append({"network_step": step_dict, "player_response": response})
        if step.is_final:
            if response.get("type") != "player_step_result" or response.get("actions"):
                raise ValueError("Expected a final player result without actions")
            return response["result"]
        if response.get("type") != "player_actions":
            raise ValueError(f"Unexpected player response type {response.get('type')!r}")
        for action in response["actions"]:
            key = (action.get("ue_id"), action.get("request_id"))
            if key[0] not in ue_ids or not isinstance(key[1], str) or not key[1]:
                raise ValueError(f"Invalid request identity {key}")
            if action.get("op") == "submit_request":
                size = action.get("bytes_total")
                if key in sizes:
                    raise ValueError(f"Duplicate request ID {key}")
                if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
                    raise ValueError(f"Invalid byte count for {key}")
                backend.submit_request(key[0], key[1], size)
                sizes[key] = size
                delivered[key] = 0
            elif action.get("op") == "cancel_request":
                backend.cancel_request(key[0], key[1])
            else:
                raise ValueError(f"Unknown player action {action.get('op')!r}")
    raise RuntimeError(f"Run exceeded {max_steps} steps")

"""Backend `transport_fikore`: TransportBackend from the FikoRE submodule.

The transport models, FikoreLink and the process wrapper live in
5g-network-emulator/transport/. This module only maps the experiment
configuration onto them. Setup follows transport/benchmarks/validate_sfv.py
in the FikoRE repository.
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fikore_transport.backend import BackendConfig, TransportBackend
from fikore_transport.cc import Cubic, Reno
from fikore_transport.emulator import Emulator, EmulatorConfig
from fikore_transport.fikore_link import FikoreLink
from fikore_transport.link import LoopbackConfig, LoopbackLink

FIKORE_ROOT = Path(__file__).resolve().parents[2] / "5g-network-emulator"

CONGESTION_CONTROLLERS = {"cubic": Cubic, "reno": Reno}


@dataclass(frozen=True)
class TransportFikoreConfig:
    """Settings of the `network` block for `transport_fikore`."""

    link: str = "fikore"
    """`fikore`, or `loopback` for tests without the emulator"""
    transport: str = "tcp"
    """`tcp`, or `ideal` for the diagnostic fixed-window transport"""
    congestion_control: str = "cubic"
    receive_window_bytes: int = 128 * 1024
    step_ms: int = 10
    """Duration of one NetworkStep towards the player in milliseconds"""
    telemetry_interval_ms: int = 10
    """Interval of NetworkTelemetryReceived events; a multiple of step_ms"""
    fikore_binary: str = str(FIKORE_ROOT / "bin" / "fikore")
    fikore_base_ini: str = str(FIKORE_ROOT / "config" / "control_demo.ini")
    delay_budget_s: float = 30.0
    """PDCP delay budget; high so that validation runs do not expire packets"""
    fikore_overrides: dict[str, str] = field(default_factory=dict)
    """Extra `.ini` keys written into the generated FikoRE configuration"""

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> TransportFikoreConfig:
        unknown = set(values) - set(cls.__dataclass_fields__)
        if unknown:
            raise ValueError(f"Unknown transport_fikore settings: {sorted(unknown)}")
        config = cls(**values)
        if config.link not in ("fikore", "loopback"):
            raise ValueError(f"Unknown link {config.link!r}")
        if config.congestion_control not in CONGESTION_CONTROLLERS:
            raise ValueError(f"Unknown congestion control {config.congestion_control!r}")
        if config.step_ms <= 0 or config.receive_window_bytes <= 0:
            raise ValueError("step_ms and receive_window_bytes must be positive")
        if config.telemetry_interval_ms <= 0 or config.telemetry_interval_ms % config.step_ms:
            raise ValueError("telemetry_interval_ms must be a positive multiple of step_ms")
        return config


class TransportFikoreBackend(TransportBackend):
    """TransportBackend that also owns the emulator's working directory."""

    name = "transport_fikore"

    def __init__(
        self,
        config: TransportFikoreConfig,
        *,
        ue_ids: list[int],
        duration_s: float,
        output_dir: Path,
    ) -> None:
        self.settings = config
        self.work_dir = Path(tempfile.mkdtemp(prefix="capcsp-fikore-"))
        self.output_dir = output_dir
        if config.link == "fikore":
            if not Path(config.fikore_binary).exists():
                raise FileNotFoundError(
                    f"FikoRE binary not found at {config.fikore_binary}; build it with `make` in 5g-network-emulator"
                )
            emulator = Emulator(
                EmulatorConfig(
                    binary=config.fikore_binary,
                    base_ini=config.fikore_base_ini,
                    socket_path=str(self.work_dir / "control.sock"),
                    duration_s=duration_s + 1.0,
                    work_dir=str(FIKORE_ROOT),
                    n_ues=len(ue_ids),
                    delay_budget_s=config.delay_budget_s,
                    log_path=str(output_dir / "fikore.log"),
                    extra=dict(config.fikore_overrides),
                )
            )
            # FikoRE numbers UEs from 0; map sorted experiment UE IDs onto them
            ue_id_map = {ue_id: index for index, ue_id in enumerate(sorted(ue_ids))}
            link = FikoreLink(emulator, flow_to_ue={}, ue_id_map=ue_id_map)
        else:
            link = LoopbackLink(LoopbackConfig())
        super().__init__(
            link,
            BackendConfig(
                window_ttis=config.step_ms,
                horizon_ttis=round(duration_s * 1000),
                rwnd=config.receive_window_bytes,
                cc_factory=CONGESTION_CONTROLLERS[config.congestion_control],
                transport=config.transport,
                telemetry_every_windows=config.telemetry_interval_ms // config.step_ms,
            ),
        )

    def accounting(self) -> dict[str, Any] | None:
        """Byte conservation counters of the link, or None for the loopback link."""
        link = self.link
        if not isinstance(link, FikoreLink):
            return None
        accounted = sum(link.terminal_bytes.values()) + link.in_flight_bytes
        return {
            "submitted_bytes": link.submitted_bytes,
            "terminal_bytes": dict(link.terminal_bytes),
            "in_flight_bytes": link.in_flight_bytes,
            "bytes_conserved": accounted == link.submitted_bytes,
        }

    def close(self) -> None:
        super().close()
        effective_ini = self.work_dir / "cosim-run.ini"
        if effective_ini.exists():
            shutil.copy(effective_ini, self.output_dir / "fikore-effective.ini")
        shutil.rmtree(self.work_dir, ignore_errors=True)

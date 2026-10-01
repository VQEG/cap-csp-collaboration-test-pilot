"""FikoRE condition-path and timeline replay configuration."""

import json
from pathlib import Path

import pytest

from capcsp.network.transport_fikore import (
    REPO_ROOT,
    TransportFikoreConfig,
    load_control_timeline,
)


def test_relative_base_ini_is_resolved_from_repository_root() -> None:
    config = TransportFikoreConfig.from_dict(
        {
            "fikore_base_ini": "configs/fikore/c1_healthy_5g.ini",
            "study_ues": ["studyVqeg"],
            "delay_budget_s": None,
            "random_v": None,
            "ack_over_link": True,
        }
    )
    assert config.fikore_base_ini == str(
        (REPO_ROOT / "configs/fikore/c1_healthy_5g.ini").resolve()
    )
    assert config.study_ues == ["studyVqeg"]
    assert config.delay_budget_s is None
    assert config.random_v is None
    assert config.ack_over_link is True


def test_timeline_loader_rounds_expands_and_preserves_fifo(
    tmp_path: Path,
) -> None:
    timeline = tmp_path / "timeline.ndjson"
    messages = [
        {
            "id": 1,
            "at_t": 0.0015,
            "cmds": [
                {
                    "target": "ue/studyVqeg",
                    "set": {"dl.sinr_offset_db": -6.0},
                },
                {
                    "target": "ue/backgroundVqeg_0",
                    "set": {"enabled": False},
                },
            ],
        },
        {
            "id": 2,
            "at_t": 99.0,
            "at_tti": 7,
            "cmds": [
                {
                    "target": "ue/studyVqeg",
                    "set": {"dl.rmax_mbps": 25.0},
                }
            ],
        },
    ]
    timeline.write_text(
        "".join(json.dumps(message) + "\n" for message in messages)
    )

    scheduled = load_control_timeline(
        timeline,
        study_group="studyVqeg",
        study_targets=["studyVqeg_0", "studyVqeg_1"],
    )
    assert [
        (item.at_tti, item.target, item.params)
        for item in scheduled
    ] == [
        (2, "ue/studyVqeg_0", {"dl.sinr_offset_db": -6.0}),
        (2, "ue/studyVqeg_1", {"dl.sinr_offset_db": -6.0}),
        (2, "ue/backgroundVqeg_0", {"enabled": False}),
        (7, "ue/studyVqeg_0", {"dl.rmax_mbps": 25.0}),
        (7, "ue/studyVqeg_1", {"dl.rmax_mbps": 25.0}),
    ]


@pytest.mark.parametrize(
    "message",
    [
        {"at_tti": -1, "cmds": [{"target": "ue/0", "set": {"priority": 1}}]},
        {"at_t": float("nan"), "cmds": [{"target": "ue/0", "set": {"priority": 1}}]},
        {"at_tti": 0, "cmds": [{"op": "get", "target": "ue/0"}]},
        {"at_tti": 0, "cmds": [{"target": "", "set": {"priority": 1}}]},
        {"at_tti": 0, "cmds": [{"target": "ue/0", "set": {}}]},
    ],
)
def test_timeline_loader_rejects_malformed_commands(
    tmp_path: Path,
    message: dict,
) -> None:
    timeline = tmp_path / "bad.ndjson"
    timeline.write_text(json.dumps(message) + "\n")
    with pytest.raises(ValueError):
        load_control_timeline(
            timeline,
            study_group="studyVqeg",
            study_targets=["studyVqeg"],
        )

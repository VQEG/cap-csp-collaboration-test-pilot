"""Parametric single-cell 5G scenario and Poisson session-arrival synthesizer for FikoRE.

Synthesizes a complete FikoRE `.ini` scenario, a deterministic `.ndjson` control timeline
(session arrivals, departures, spatial coordinates, and optional study-UE trajectory), and
application-paced TCP background rates from a compact declarative dictionary. Synthesis is
purely deterministic from ``Global.seed`` (keyed via ``SHA-256("capcsp-parametric-cell::<seed>")``),
so paired player configurations and re-runs with the same seed reproduce byte-identical `.ini`
and `.ndjson` artifacts without checking static timeline files into git.

Proportional-fair scheduling (`metric_type: 6`) runs unconstrained without per-UE `rmax` caps,
unless the optional ``study_dl_rmax_mbps`` knob installs one static downlink cap on the study UE.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

# HARQ framing efficiency factor matching FikoRE downlink grant utilization on UMa n78.
_HARQ_EFFICIENCY_FACTOR = 0.985

STUDY_ZONE_DISTANCES_M: dict[str, float] = {
    "good": 151.255881,
    "mid": 350.0,
    "edge": 650.0,
}

VALID_BANDWIDTHS_MHZ = (10, 20, 40, 60, 80, 100)
VALID_STUDY_POSITIONS = ("good", "mid", "edge", "custom")
VALID_STUDY_MOBILITIES = ("static", "urban_bus", "vehicular_traverse")
VALID_BG_SPATIAL = ("none", "homogeneous_ring", "cell_disk")
VALID_ARRIVAL_MODES = ("poisson", "mmpp")

CORE6_PRESET_IDS: tuple[str, ...] = ("M01", "M04", "M05", "M07", "M09", "M10")

# Deterministic urban bus stop-and-go cycle: cruise at `study_speed_kmh`, then dwell at a stop.
BUS_DRIVE_PHASE_S = 15.0
BUS_STOP_DWELL_S = 10.0
BUS_CYCLE_S = BUS_DRIVE_PHASE_S + BUS_STOP_DWELL_S
# Interval between study-UE position waypoints in the synthesized control timeline.
STUDY_WAYPOINT_PERIOD_TTI = 250

DEFAULT_URBAN_BUS_SPEED_KMH = 25.0
DEFAULT_VEHICULAR_TRAVERSE_SPEED_KMH = 73.26

# Calibrated UMa n78 (3.5 GHz, 20 MHz, numerology 1, TDD 7/3/54) points on
# include/maps_scenarios/macroscopic_fading_map_URBAN_MACROCELL_3.5.json:
# each tuple is (x_m, y_m, standalone_dl_capacity_20mhz_mbps).
GOOD_RING_POOL: tuple[tuple[float, float, float], ...] = (
    (151.256, 0.0, 66.71),
    (150.932, 9.893, 66.71),
    (149.962, 19.743, 62.27),
    (143.229, 48.62, 64.49),
    (139.742, 57.883, 66.71),
    (135.657, 66.899, 66.71),
    (130.991, 75.628, 66.71),
    (125.765, 84.033, 66.71),
    (119.999, 92.079, 66.71),
    (113.72, 99.73, 66.71),
    (106.954, 106.954, 66.71),
    (99.73, 113.72, 66.71),
    (75.628, 130.991, 66.71),
    (66.899, 135.657, 66.71),
    (57.883, 139.742, 66.71),
    (48.62, 143.229, 66.71),
    (39.148, 146.102, 66.71),
    (29.509, 148.35, 66.71),
    (19.743, 149.962, 64.49),
    (-9.893, 150.932, 66.71),
    (-19.743, 149.962, 66.71),
    (-29.509, 148.35, 66.71),
    (-39.148, 146.102, 66.71),
    (-48.62, 143.229, 66.71),
    (-57.883, 139.742, 66.71),
    (-66.899, 135.657, 66.71),
    (-75.628, 130.991, 66.71),
    (-84.033, 125.765, 66.71),
    (-92.079, 119.999, 66.71),
    (-99.73, 113.72, 66.71),
    (-106.954, 106.954, 66.71),
    (-113.72, 99.73, 66.71),
    (-119.999, 92.079, 66.71),
    (-125.765, 84.033, 66.71),
    (-130.991, 75.628, 66.71),
    (-135.657, 66.899, 66.71),
    (-139.742, 57.883, 66.71),
    (-143.229, 48.62, 66.71),
    (-146.102, 39.148, 66.71),
    (-148.35, 29.509, 66.71),
    (-149.962, 19.743, 66.71),
    (-150.932, 9.893, 66.71),
    (-151.256, 0.0, 66.71),
    (-150.932, -9.893, 66.71),
    (-149.962, -19.743, 66.71),
    (-148.35, -29.509, 66.71),
    (-146.102, -39.148, 66.71),
    (-143.229, -48.62, 66.71),
    (-139.742, -57.883, 66.71),
    (-135.657, -66.899, 66.71),
    (-130.991, -75.628, 66.71),
    (-113.72, -99.73, 66.71),
    (-106.954, -106.954, 66.71),
    (-99.73, -113.72, 66.71),
    (-92.079, -119.999, 66.71),
    (-84.033, -125.765, 66.71),
    (-75.628, -130.991, 66.71),
    (-66.899, -135.657, 66.71),
    (-57.883, -139.742, 66.71),
    (-48.62, -143.229, 66.71),
    (-39.148, -146.102, 66.71),
    (-29.509, -148.35, 66.71),
    (-19.743, -149.962, 66.71),
    (-9.893, -150.932, 66.71),
    (0.0, -151.256, 66.71),
    (9.893, -150.932, 66.71),
    (19.743, -149.962, 66.71),
    (29.509, -148.35, 66.71),
    (39.148, -146.102, 66.71),
    (48.62, -143.229, 66.71),
    (57.883, -139.742, 66.71),
    (66.899, -135.657, 66.71),
    (75.628, -130.991, 66.71),
    (84.033, -125.765, 66.71),
    (92.079, -119.999, 66.71),
    (99.73, -113.72, 66.71),
    (106.954, -106.954, 66.71),
    (113.72, -99.73, 66.71),
    (119.999, -92.079, 66.71),
    (125.765, -84.033, 66.71),
    (130.991, -75.628, 66.71),
    (135.657, -66.899, 66.71),
    (139.742, -57.883, 66.71),
    (143.229, -48.62, 66.71),
    (146.102, -39.148, 66.71),
    (148.35, -29.509, 66.71),
    (149.962, -19.743, 66.71),
    (150.932, -9.893, 66.71),
)

CELL_DISK_POOL: tuple[tuple[float, float, float], ...] = (
    (-574.574, -105.135, 35.15),
    (-85.66, -256.141, 66.71),
    (45.295, -434.624, 15.27),
    (-73.721, 474.199, 53.05),
    (522.932, -53.268, 17.24),
    (40.504, -157.769, 66.71),
    (-258.792, 340.806, 29.92),
    (-377.034, -414.306, 24.59),
    (159.272, 457.914, 46.07),
    (159.128, -157.371, 46.07),
    (-50.443, -403.313, 46.07),
    (-34.24, -105.915, 66.71),
    (-276.743, 56.1, 56.08),
    (-325.344, 291.788, 32.51),
    (91.687, -23.717, 66.71),
    (-470.279, -237.967, 17.24),
    (274.094, 501.193, 40.74),
    (257.231, 175.104, 46.07),
    (-171.598, -270.946, 66.71),
    (-46.254, 10.046, 66.71),
    (-598.281, 115.52, 43.38),
    (-597.608, -111.242, 37.94),
    (-415.642, 102.842, 23.15),
    (126.266, -480.647, 23.15),
    (85.02, -25.385, 66.71),
    (409.214, 28.837, 21.67),
    (-156.905, 258.048, 66.71),
    (440.498, 356.988, 23.15),
    (-19.384, -49.288, 66.71),
    (-175.362, -125.033, 66.71),
    (-94.935, 158.204, 66.71),
    (-244.209, -478.948, 46.07),
    (151.77, -322.14, 64.49),
    (424.455, 326.897, 29.92),
    (-344.026, 216.448, 13.3),
    (-158.55, 353.439, 43.38),
    (-343.501, -122.975, 66.71),
    (-169.682, 83.588, 66.71),
    (-43.415, 153.157, 66.71),
    (-174.997, -241.143, 66.71),
    (307.297, -405.012, 13.3),
    (-444.72, 300.975, 40.74),
    (-51.9, 99.911, 66.71),
    (421.291, -191.132, 32.51),
    (-253.724, -253.79, 43.38),
    (407.971, 197.139, 27.28),
    (-248.464, 20.432, 66.71),
    (-159.13, -212.787, 66.71),
    (-487.742, -153.768, 13.3),
    (424.177, 16.493, 23.15),
    (103.3, -496.334, 21.67),
    (255.81, 402.277, 53.05),
    (518.473, 239.089, 46.07),
    (255.053, 144.315, 66.71),
    (222.628, -533.4, 23.15),
    (198.583, -118.645, 37.94),
    (271.539, -400.309, 24.59),
    (47.552, 179.416, 66.71),
    (165.592, 107.2, 66.71),
    (408.866, 259.756, 35.15),
    (171.457, -534.359, 15.27),
    (290.225, -344.86, 27.28),
    (167.922, 239.481, 29.92),
    (81.729, -544.456, 5.42),
    (-338.092, -169.758, 64.49),
    (-342.54, -484.976, 10.59),
    (378.164, 276.738, 50.03),
    (353.709, 47.61, 23.15),
    (-469.022, 144.324, 56.08),
    (366.877, -51.827, 40.74),
    (-85.362, 278.965, 53.05),
    (-322.277, -460.805, 32.51),
    (-183.095, 524.401, 7.9),
    (453.524, -30.438, 24.59),
    (-326.69, 325.803, 46.07),
    (3.932, -408.866, 23.15),
    (-536.86, 228.616, 29.92),
    (92.524, -130.447, 66.71),
    (-221.24, 530.626, 10.59),
    (176.015, 500.613, 32.51),
    (-211.026, 22.705, 66.71),
    (-123.896, 155.297, 66.71),
    (-143.644, -208.905, 66.71),
    (-240.505, -304.072, 46.07),
    (520.295, -12.316, 64.49),
    (-341.773, -110.441, 62.27),
    (445.544, 203.772, 46.07),
    (-302.15, -371.254, 46.07),
    (417.414, 392.17, 7.9),
    (-404.641, -428.517, 10.59),
    (28.18, -616.491, 7.9),
    (-90.619, 465.52, 59.18),
    (131.958, 382.812, 24.59),
    (325.514, 235.168, 46.07),
    (-390.269, 344.426, 35.15),
    (-174.973, -242.109, 66.71),
    (-426.415, 125.709, 29.92),
    (-308.684, -92.493, 66.71),
    (541.413, 153.039, 17.24),
    (293.344, 121.634, 46.07),
    (355.446, 152.161, 46.07),
    (-429.266, -412.479, 10.59),
    (91.72, -17.056, 66.71),
    (-381.849, -334.517, 29.92),
    (493.046, 316.586, 23.15),
    (610.74, 64.538, 13.3),
    (-301.012, -44.479, 64.49),
    (-324.882, 265.654, 48.02),
    (55.095, -514.484, 21.67),
    (414.394, 374.303, 10.59),
    (-495.269, -339.486, 7.9),
    (-450.605, -90.806, 10.59),
    (-132.386, -448.769, 7.9),
    (14.743, 460.869, 17.24),
    (-108.534, 542.64, 10.59),
    (510.759, -277.432, 59.18),
    (-174.528, -348.679, 40.74),
    (-461.552, 216.688, 50.03),
    (615.144, -62.574, 5.42),
    (-371.201, -77.981, 64.49),
    (575.755, 208.747, 23.15),
    (226.676, 358.973, 46.07),
    (-601.707, 58.777, 21.67),
    (-524.437, -320.788, 7.9),
    (-395.876, -126.145, 50.03),
    (-2.13, -173.271, 66.71),
    (-278.424, -316.703, 32.51),
    (-259.277, 38.749, 66.71),
    (-180.192, -233.211, 66.71),
    (106.6, -168.78, 62.27),
    (43.704, 237.947, 66.71),
    (-164.817, 494.134, 24.59),
    (-320.831, 450.154, 19.46),
    (293.795, 248.263, 46.07),
    (470.62, -164.701, 23.15),
    (372.656, -126.73, 27.28),
    (237.571, 330.825, 56.08),
    (-331.514, -451.528, 23.15),
    (27.987, 269.246, 46.07),
    (317.075, -303.661, 27.28),
    (122.476, -172.54, 62.27),
    (-265.326, -334.534, 32.51),
    (51.816, 64.351, 66.71),
    (-172.458, 308.47, 53.05),
    (455.734, -384.187, 19.46),
    (-80.817, 579.257, 10.59),
    (-499.759, 10.889, 23.15),
    (458.173, 248.678, 35.15),
    (523.705, 55.556, 24.59),
    (-444.023, -184.504, 46.07),
    (-573.673, 178.647, 10.59),
    (80.7, 328.046, 37.94),
    (-281.676, -339.083, 24.59),
    (-63.454, -45.515, 66.71),
    (75.485, 567.866, 7.9),
    (3.007, 334.275, 48.02),
    (301.393, -294.506, 32.51),
    (53.754, 573.556, 13.3),
    (-343.315, 466.9, 32.51),
    (-344.409, -25.135, 43.38),
    (111.418, -388.499, 43.38),
    (177.07, -64.291, 66.71),
    (481.499, -350.799, 23.15),
    (223.611, 502.63, 46.07),
    (-455.525, 18.568, 48.02),
    (-185.28, -561.868, 46.07),
    (520.797, -174.15, 15.27),
    (66.952, -593.929, 7.9),
    (238.67, -238.609, 37.94),
    (-429.427, -372.398, 21.67),
    (-596.434, 177.56, 23.15),
    (-287.516, 454.795, 10.59),
    (574.621, -176.077, 5.42),
    (215.53, -40.462, 66.71),
    (-340.342, 306.516, 46.07),
    (-206.403, 447.586, 35.15),
    (-591.653, -181.458, 27.28),
    (-55.923, 482.355, 43.38),
    (453.595, -69.67, 24.59),
    (-277.15, 504.703, 7.9),
    (-410.258, -33.584, 23.15),
    (538.475, -210.675, 5.42),
    (-38.425, -570.73, 21.67),
    (443.255, 58.532, 32.51),
    (-541.865, 125.031, 21.67),
    (122.478, 431.686, 17.24),
    (178.935, -128.083, 50.03),
    (-609.749, 76.905, 23.15),
    (494.398, -358.87, 23.15),
    (109.009, 360.522, 23.15),
    (337.399, -79.041, 53.05),
    (60.075, 85.125, 66.71),
    (-227.063, 331.893, 40.74),
    (-291.953, -327.086, 32.51),
    (-185.08, -368.773, 40.74),
    (-118.061, 484.559, 59.18),
    (536.605, -250.059, 35.15),
    (-201.138, 262.591, 43.38),
    (417.519, -250.839, 40.74),
    (-206.693, 162.03, 62.27),
    (-523.307, 68.73, 13.3),
    (-165.724, -387.405, 35.15),
    (236.521, 85.378, 46.07),
    (-398.739, 282.038, 37.94),
    (-94.616, 536.659, 10.59),
    (205.761, -426.681, 15.27),
    (-434.259, -172.598, 50.03),
    (-512.687, 41.882, 10.59),
    (135.456, -539.722, 15.27),
    (318.098, -183.848, 66.71),
    (-40.544, -3.907, 66.71),
    (-162.503, -230.732, 66.71),
    (289.259, -91.708, 53.05),
    (248.415, -349.827, 27.28),
    (-186.099, -117.681, 66.71),
    (-177.592, -553.354, 37.94),
    (461.232, 29.701, 43.38),
    (106.878, -34.656, 66.71),
    (-118.411, 8.098, 66.71),
    (-70.793, -362.753, 59.18),
    (508.225, -116.617, 5.42),
    (340.283, -122.315, 37.94),
    (-197.523, 481.521, 24.59),
    (-33.785, -582.088, 17.24),
    (579.213, 163.876, 10.59),
    (-587.481, 103.378, 32.51),
    (402.647, -455.682, 19.46),
    (-613.636, 40.724, 23.15),
    (-280.664, -464.732, 43.38),
    (-98.603, -598.419, 32.51),
    (196.458, 312.519, 56.08),
    (407.922, -369.052, 23.15),
    (39.277, -47.098, 66.71),
    (-579.79, 48.414, 19.46),
    (93.118, 556.231, 5.42),
    (-11.379, -403.173, 35.15),
    (178.513, -210.58, 56.08),
    (-484.461, -148.441, 10.59),
    (391.213, 396.469, 10.59),
    (-491.32, -185.864, 23.15),
    (-479.383, -5.305, 29.92),
    (514.305, -233.43, 19.46),
    (-306.789, -518.739, 15.27),
    (586.134, 40.041, 21.67),
    (260.355, -539.686, 32.51),
    (-142.293, 33.015, 66.71),
    (-62.197, -189.304, 66.71),
    (-23.912, 243.768, 66.71),
    (-320.192, -491.431, 66.71),
    (-559.984, 74.315, 13.3),
    (578.762, 170.051, 21.67),
    (62.975, 1.201, 66.71),
    (-377.248, 62.961, 46.07),
    (462.121, -74.624, 24.59),
    (-50.447, 74.327, 66.71),
    (470.996, 241.935, 56.08),
)

_DEFAULT_CUSTOM_SPEC: dict[str, Any] = {
    "preset": "custom",
    "bandwidth_mhz": 20,
    "study_position": "good",
    "study_distance_m": STUDY_ZONE_DISTANCES_M["good"],
    "study_mobility": "static",
    "study_speed_kmh": 0.0,
    "traverse_min_distance_m": STUDY_ZONE_DISTANCES_M["good"],
    "traverse_max_distance_m": 660.0,
    "study_dl_rmax_mbps": None,
    "load_rho": 0.50,
    "bg_spatial": "cell_disk",
    "bg_max_distance_m": 630.0,
    "bg_bitrate_mbps": 4.0,
    "arrival_mode": "poisson",
    "mean_hold_s": 8.0,
    "burst_amplitude": 0.65,
    "burst_regime_s": 14.0,
    "backhaul_delay_ms": 10.0,
    "backhaul_jitter_ms": 1.0,
}

PARAMETRIC_CELL_PRESETS: dict[str, dict[str, Any]] = {
    "M01": {
        **_DEFAULT_CUSTOM_SPEC,
        "preset": "M01",
        "load_rho": 0.0,
        "bg_spatial": "none",
    },
    "M02": {
        **_DEFAULT_CUSTOM_SPEC,
        "preset": "M02",
        "load_rho": 0.50,
        "bg_spatial": "homogeneous_ring",
    },
    "M03": {
        **_DEFAULT_CUSTOM_SPEC,
        "preset": "M03",
        "load_rho": 0.75,
        "bg_spatial": "homogeneous_ring",
    },
    "M04": {
        **_DEFAULT_CUSTOM_SPEC,
        "preset": "M04",
        "load_rho": 1.00,
        "bg_spatial": "homogeneous_ring",
    },
    "M05": {
        **_DEFAULT_CUSTOM_SPEC,
        "preset": "M05",
        "load_rho": 1.00,
        "bg_spatial": "homogeneous_ring",
        "arrival_mode": "mmpp",
        "mean_hold_s": 12.0,
        "burst_amplitude": 0.65,
        "burst_regime_s": 14.0,
    },
    "M06": {
        **_DEFAULT_CUSTOM_SPEC,
        "preset": "M06",
        "load_rho": 1.00,
        "bg_spatial": "cell_disk",
    },
    "M07": {
        **_DEFAULT_CUSTOM_SPEC,
        "preset": "M07",
        "study_position": "mid",
        "study_distance_m": STUDY_ZONE_DISTANCES_M["mid"],
        "load_rho": 1.00,
        "bg_spatial": "cell_disk",
    },
    "M08": {
        **_DEFAULT_CUSTOM_SPEC,
        "preset": "M08",
        "study_position": "edge",
        "study_distance_m": STUDY_ZONE_DISTANCES_M["edge"],
        "load_rho": 0.50,
        "bg_spatial": "cell_disk",
    },
    "M09": {
        **_DEFAULT_CUSTOM_SPEC,
        "preset": "M09",
        "study_position": "edge",
        "study_distance_m": STUDY_ZONE_DISTANCES_M["edge"],
        "load_rho": 0.75,
        "bg_spatial": "cell_disk",
    },
    "M10": {
        **_DEFAULT_CUSTOM_SPEC,
        "preset": "M10",
        "study_position": "good",
        "study_distance_m": STUDY_ZONE_DISTANCES_M["good"],
        "study_mobility": "vehicular_traverse",
        "study_speed_kmh": 73.26,
        "traverse_min_distance_m": STUDY_ZONE_DISTANCES_M["good"],
        "traverse_max_distance_m": 660.0,
        "load_rho": 0.50,
        "bg_spatial": "cell_disk",
    },
    "M11": {
        **_DEFAULT_CUSTOM_SPEC,
        "preset": "M11",
        "study_position": "custom",
        "study_distance_m": 220.0,
        "study_mobility": "urban_bus",
        "study_speed_kmh": DEFAULT_URBAN_BUS_SPEED_KMH,
        "traverse_min_distance_m": 220.0,
        "traverse_max_distance_m": 650.0,
        "load_rho": 0.50,
        "bg_spatial": "cell_disk",
    },
    "custom": dict(_DEFAULT_CUSTOM_SPEC),
}


def _finite_number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"parametric_cell.{name} must be a finite number")
    return float(value)


@dataclass(frozen=True)
class ParametricCellConfig:
    """Validated parametric 5G cell model settings."""

    preset: str = "custom"
    bandwidth_mhz: int = 20
    study_position: str = "good"
    study_distance_m: float = STUDY_ZONE_DISTANCES_M["good"]
    study_mobility: str = "static"
    study_speed_kmh: float = 0.0
    traverse_min_distance_m: float = STUDY_ZONE_DISTANCES_M["good"]
    traverse_max_distance_m: float = 660.0
    study_dl_rmax_mbps: float | None = None
    """Optional static downlink rate cap of the study UE in Mbps (`None` = uncapped)."""
    load_rho: float = 0.50
    bg_spatial: str = "cell_disk"
    bg_max_distance_m: float = 630.0
    bg_bitrate_mbps: float = 4.0
    arrival_mode: str = "poisson"
    mean_hold_s: float = 8.0
    burst_amplitude: float = 0.65
    burst_regime_s: float = 14.0
    backhaul_delay_ms: float = 10.0
    backhaul_jitter_ms: float = 1.0

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> ParametricCellConfig:
        if not isinstance(values, dict):
            raise ValueError("parametric_cell must be an object")
        known = set(cls.__dataclass_fields__)
        unknown = set(values) - known
        if unknown:
            raise ValueError(f"Unknown parametric_cell settings: {sorted(unknown)}")

        preset = values.get("preset", "custom")
        if not isinstance(preset, str) or preset not in PARAMETRIC_CELL_PRESETS:
            raise ValueError(
                f"parametric_cell.preset must be one of {sorted(PARAMETRIC_CELL_PRESETS)}"
            )
        merged = dict(PARAMETRIC_CELL_PRESETS[preset])
        merged.update(values)

        if "study_position" in values and "study_distance_m" not in values:
            pos = values["study_position"]
            if pos in STUDY_ZONE_DISTANCES_M:
                merged["study_distance_m"] = STUDY_ZONE_DISTANCES_M[pos]
        elif "study_distance_m" in values and "study_position" not in values:
            merged["study_position"] = "custom"

        if "study_mobility" in values and "study_speed_kmh" not in values:
            mob = values["study_mobility"]
            if mob == "static":
                merged["study_speed_kmh"] = 0.0
            elif mob == "urban_bus":
                merged["study_speed_kmh"] = DEFAULT_URBAN_BUS_SPEED_KMH
            elif mob == "vehicular_traverse":
                merged["study_speed_kmh"] = DEFAULT_VEHICULAR_TRAVERSE_SPEED_KMH

        load_rho = _finite_number(merged["load_rho"], "load_rho")
        if load_rho > 0.0 and merged["bg_spatial"] == "none" and "bg_spatial" not in values:
            merged["bg_spatial"] = "cell_disk"

        bw_raw = merged["bandwidth_mhz"]
        if isinstance(bw_raw, bool) or not isinstance(bw_raw, int) or bw_raw not in VALID_BANDWIDTHS_MHZ:
            raise ValueError(f"parametric_cell.bandwidth_mhz must be one of {VALID_BANDWIDTHS_MHZ}")
        if merged["study_position"] not in VALID_STUDY_POSITIONS:
            raise ValueError(f"parametric_cell.study_position must be one of {VALID_STUDY_POSITIONS}")
        if merged["study_mobility"] not in VALID_STUDY_MOBILITIES:
            raise ValueError(f"parametric_cell.study_mobility must be one of {VALID_STUDY_MOBILITIES}")
        if merged["bg_spatial"] not in VALID_BG_SPATIAL:
            raise ValueError(f"parametric_cell.bg_spatial must be one of {VALID_BG_SPATIAL}")
        if merged["arrival_mode"] not in VALID_ARRIVAL_MODES:
            raise ValueError(f"parametric_cell.arrival_mode must be one of {VALID_ARRIVAL_MODES}")

        study_distance_m = _finite_number(merged["study_distance_m"], "study_distance_m")
        if not 10.0 <= study_distance_m <= 850.0:
            raise ValueError("parametric_cell.study_distance_m must be between 10 and 850 m")

        study_speed_kmh = _finite_number(merged["study_speed_kmh"], "study_speed_kmh")
        if study_speed_kmh < 0.0 or study_speed_kmh > 250.0:
            raise ValueError("parametric_cell.study_speed_kmh must be between 0 and 250 km/h")
        if merged["study_mobility"] != "static" and study_speed_kmh <= 0.0:
            raise ValueError(
                f"parametric_cell.study_speed_kmh must be positive for {merged['study_mobility']}"
            )

        trav_min = _finite_number(merged["traverse_min_distance_m"], "traverse_min_distance_m")
        trav_max = _finite_number(merged["traverse_max_distance_m"], "traverse_max_distance_m")
        if not (10.0 <= trav_min <= 850.0 and 10.0 <= trav_max <= 850.0):
            raise ValueError("parametric_cell traverse distances must be between 10 and 850 m")
        if merged["study_mobility"] in ("vehicular_traverse", "urban_bus") and abs(trav_max - trav_min) < 1.0:
            raise ValueError("parametric_cell traverse_min_distance_m and traverse_max_distance_m must differ")

        study_dl_rmax_mbps: float | None = None
        if merged.get("study_dl_rmax_mbps") is not None:
            study_dl_rmax_mbps = _finite_number(merged["study_dl_rmax_mbps"], "study_dl_rmax_mbps")
            if not 0.1 <= study_dl_rmax_mbps <= 1000.0:
                raise ValueError("parametric_cell.study_dl_rmax_mbps must be between 0.1 and 1000.0 Mbps when set")

        if not 0.0 <= load_rho <= 2.0:
            raise ValueError("parametric_cell.load_rho must be between 0.0 and 2.0")

        bg_max_distance_m = _finite_number(merged["bg_max_distance_m"], "bg_max_distance_m")
        if not 120.0 <= bg_max_distance_m <= 700.0:
            raise ValueError("parametric_cell.bg_max_distance_m must be between 120 and 700 m")

        bg_bitrate_mbps = _finite_number(merged["bg_bitrate_mbps"], "bg_bitrate_mbps")
        if not 0.1 <= bg_bitrate_mbps <= 100.0:
            raise ValueError("parametric_cell.bg_bitrate_mbps must be between 0.1 and 100.0 Mbps")

        mean_hold_s = _finite_number(merged["mean_hold_s"], "mean_hold_s")
        if not 0.5 <= mean_hold_s <= 300.0:
            raise ValueError("parametric_cell.mean_hold_s must be between 0.5 and 300.0 s")

        burst_amplitude = _finite_number(merged["burst_amplitude"], "burst_amplitude")
        if not 0.0 <= burst_amplitude <= 0.95:
            raise ValueError("parametric_cell.burst_amplitude must be between 0.0 and 0.95")

        burst_regime_s = _finite_number(merged["burst_regime_s"], "burst_regime_s")
        if not 1.0 <= burst_regime_s <= 120.0:
            raise ValueError("parametric_cell.burst_regime_s must be between 1.0 and 120.0 s")

        backhaul_delay_ms = _finite_number(merged["backhaul_delay_ms"], "backhaul_delay_ms")
        backhaul_jitter_ms = _finite_number(merged["backhaul_jitter_ms"], "backhaul_jitter_ms")
        if backhaul_delay_ms < 0.0 or backhaul_jitter_ms < 0.0:
            raise ValueError("parametric_cell backhaul delay and jitter must not be negative")

        return cls(
            preset=preset,
            bandwidth_mhz=bw_raw,
            study_position=merged["study_position"],
            study_distance_m=study_distance_m,
            study_mobility=merged["study_mobility"],
            study_speed_kmh=study_speed_kmh,
            traverse_min_distance_m=trav_min,
            traverse_max_distance_m=trav_max,
            study_dl_rmax_mbps=study_dl_rmax_mbps,
            load_rho=load_rho,
            bg_spatial=merged["bg_spatial"],
            bg_max_distance_m=bg_max_distance_m,
            bg_bitrate_mbps=bg_bitrate_mbps,
            arrival_mode=merged["arrival_mode"],
            mean_hold_s=mean_hold_s,
            burst_amplitude=burst_amplitude,
            burst_regime_s=burst_regime_s,
            backhaul_delay_ms=backhaul_delay_ms,
            backhaul_jitter_ms=backhaul_jitter_ms,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SynthesizedCell:
    """Materialized FikoRE files and background TCP rates for one run."""

    ini_path: Path
    timeline_path: Path | None
    background_iperf_ues: dict[str, float]
    pool_ue_count: int
    mean_active_bg_ues: float
    session_count: int


def _seeded_rng(seed: int) -> random.Random:
    digest = hashlib.sha256(f"capcsp-parametric-cell::{seed}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def _spatial_pool_and_mean_share(
    config: ParametricCellConfig,
) -> tuple[list[tuple[float, float]], float]:
    """Return candidate `(x_m, y_m)` points and mean downlink RB share per active background UE."""
    bw_scale = config.bandwidth_mhz / 20.0
    if config.bg_spatial == "homogeneous_ring":
        source = list(GOOD_RING_POOL)
    else:
        source = [
            pt for pt in CELL_DISK_POOL if math.hypot(pt[0], pt[1]) <= config.bg_max_distance_m
        ]
        if len(source) < 8:
            source = list(CELL_DISK_POOL[:8])

    shares = [
        min(1.0, config.bg_bitrate_mbps / max(cap_20 * bw_scale * _HARQ_EFFICIENCY_FACTOR, 1e-6))
        for _, _, cap_20 in source
    ]
    mean_share = sum(shares) / len(shares)
    return [(x, y) for x, y, _ in source], mean_share


def _generate_sessions(
    config: ParametricCellConfig,
    *,
    lam_mean: float,
    n_pool: int,
    positions: list[tuple[float, float]],
    duration_s: float,
    rng: random.Random,
) -> list[dict[str, Any]]:
    """Simulate continuous-time M/M/inf or 2-state MMPP sessions mapped onto `n_pool` UE slots."""
    horizon_tti = int(round(duration_s * 1000.0))
    if lam_mean <= 0.0 or n_pool <= 0:
        return []

    hold_s = config.mean_hold_s
    amp = config.burst_amplitude if config.arrival_mode == "mmpp" else 0.0
    pre_s = max(25.0, 3.0 * hold_s)
    t_cursor = -pre_s
    segments: list[tuple[float, float, float]] = []

    if amp <= 0.0:
        segments.append((t_cursor, duration_s, lam_mean / hold_s))
    else:
        high_state = rng.randrange(2) == 1
        while t_cursor < duration_s:
            dwell = rng.expovariate(1.0 / config.burst_regime_s)
            dwell = max(4.0, min(dwell, 25.0))
            t_next = min(duration_s, t_cursor + dwell)
            mult = (1.0 + amp) if high_state else (1.0 - amp)
            segments.append((t_cursor, t_next, (lam_mean * mult) / hold_s))
            t_cursor = t_next
            high_state = not high_state

    raw_intervals: list[tuple[float, float]] = []
    for seg_start, seg_end, rate in segments:
        if rate <= 0.0:
            continue
        t = seg_start
        while True:
            t += rng.expovariate(rate)
            if t >= seg_end:
                break
            hold = max(0.25, rng.expovariate(1.0 / hold_s))
            end_t = t + hold
            if end_t > 0.05:
                raw_intervals.append((max(0.0, t), min(duration_s, end_t)))

    raw_intervals.sort(key=lambda item: (item[0], item[1]))

    slot_free_at_tti = [0] * n_pool
    sessions: list[dict[str, Any]] = []
    for t_start, t_end in raw_intervals:
        s_tti = 0 if t_start <= 1e-6 else int(round(t_start * 1000.0))
        e_tti = int(round(t_end * 1000.0))
        if e_tti <= s_tti + 50 or s_tti >= horizon_tti - 10:
            continue
        candidates = [idx for idx in range(n_pool) if slot_free_at_tti[idx] <= s_tti]
        if not candidates:
            continue
        slot = candidates[rng.randrange(len(candidates))]
        x_m, y_m = positions[rng.randrange(len(positions))]
        slot_free_at_tti[slot] = e_tti + 25
        sessions.append(
            {
                "slot": slot,
                "start_tti": s_tti,
                "end_tti": min(e_tti, horizon_tti),
                "x_m": float(x_m),
                "y_m": float(y_m),
            }
        )
    return sessions


def _triangle_position_m(distance_m: float, d_min: float, d_max: float) -> float:
    """Reflect a cumulative travelled `distance_m` onto the corridor `[d_min, d_max]`.

    The UE starts at `d_min`, moves to `d_max`, and returns, as a triangle wave of the travelled
    distance. Works for `d_min > d_max` (the corridor is then traversed in the other direction).
    """
    span_m = abs(d_max - d_min)
    phase = (distance_m % (2.0 * span_m)) / span_m
    tri = phase if phase <= 1.0 else (2.0 - phase)
    return d_min + tri * (d_max - d_min)


def _bus_driving_time_s(t_s: float) -> tuple[float, bool]:
    """Return cumulative driving time `u(t)` and whether the bus is moving at `t_s`."""
    full_cycles, within_s = divmod(t_s, BUS_CYCLE_S)
    if within_s < BUS_DRIVE_PHASE_S:
        return full_cycles * BUS_DRIVE_PHASE_S + within_s, True
    return (full_cycles + 1.0) * BUS_DRIVE_PHASE_S, False


def _build_study_mobility_events(
    config: ParametricCellConfig,
    *,
    duration_s: float,
) -> dict[int, list[dict[str, Any]]]:
    """Build 250 ms study-UE waypoint updates along x for the scripted mobility modes.

    - `vehicular_traverse`: continuous triangle-wave traversal of `[d_min, d_max]` at constant speed.
    - `urban_bus`: the same corridor driven in stop-and-go cycles of `BUS_DRIVE_PHASE_S` cruising
      at `study_speed_kmh` followed by `BUS_STOP_DWELL_S` standing still (`speed_kmh = 0`).
    """
    by_tti: dict[int, list[dict[str, Any]]] = {}
    if config.study_mobility not in ("vehicular_traverse", "urban_bus"):
        return by_tti

    horizon_tti = int(round(duration_s * 1000.0))
    d_min = config.traverse_min_distance_m
    d_max = config.traverse_max_distance_m
    speed_ms = config.study_speed_kmh / 3.6
    for tti in range(0, horizon_tti, STUDY_WAYPOINT_PERIOD_TTI):
        t_s = tti / 1000.0
        if config.study_mobility == "vehicular_traverse":
            # Time-domain triangle wave; kept literal so that M10 artifacts stay byte-identical.
            half_period_s = abs(d_max - d_min) / speed_ms
            phase = (t_s % (2.0 * half_period_s)) / half_period_s
            tri = phase if phase <= 1.0 else (2.0 - phase)
            x_m = round(d_min + tri * (d_max - d_min), 3)
            speed_kmh = round(config.study_speed_kmh, 2)
        else:
            driving_s, is_driving = _bus_driving_time_s(t_s)
            x_m = round(_triangle_position_m(driving_s * speed_ms, d_min, d_max), 3)
            speed_kmh = round(config.study_speed_kmh, 2) if is_driving else 0.0
        by_tti.setdefault(tti, []).append(
            {
                "target": "ue/studyVqeg",
                "set": {
                    "mobility.pos_x_m": x_m,
                    "mobility.pos_y_m": 0.0,
                    "mobility.speed_kmh": speed_kmh,
                },
            }
        )
    return by_tti


def _render_parametric_ini(
    config: ParametricCellConfig,
    *,
    duration_s: float,
    seed: int,
    n_pool: int,
    timeline_path: Path | None,
) -> str:
    # Position and instantaneous speed of moving study UEs are driven by the 250 ms control
    # timeline, so the static `[UE]` header always uses `mobility_type: 0`.
    mob_type = 0
    speed_kmh = 0.0
    speed_var = 0.0

    bg_section = ""
    if n_pool > 0:
        bg_section = f"""
[UE]
ue_id: backgroundSfV
ue_type: 1
n_ues: {n_pool}
n_antennas: 1
alpha_ul: 0.8
nominal_pusch_p0: -60
set_ul_pow: true
tx_power_ul: 23
cqi_period: 5
ri_period: 5
scaling_factor: 1
random_v: true
log_freq: 100
log_ue: false
log_quality: false
log_traffic: false
log_mobility: false
traffic_type: 0
ul_target: 0.050000
dl_target: {config.bg_bitrate_mbps:.6f}
var_perc: 0.050000
pkt_size: 12000
mobility_type: 0
pos_x: 151.255881
pos_y: 0.000000
random_init: false
speed: 0.000000
speed_var: 0.000000
max_distance: 750.000000
time_target: 6.000000
time_target_var: 1.000000
priority: 1.000000
delta_metric: 1.0
delay_t_metric: 0.1
pkt_delay_budget: 0.500000
l4s_dual_queue: false
l4s_target_ms: 15
l4s_rtt_max_ms: 100
l4s_min_th_us: 800
l4s_range_us: 400
l4s_k: 2.0
l4s_classic_guard_ms: 1.0
ue_height: 1.5
ue_location_type: outdoor
building_penetration: none
"""

    if timeline_path is not None:
        control_section = f"""[Control]
enabled: true
transport: file
timeline_file: {timeline_path.resolve()}
"""
    else:
        control_section = """[Control]
enabled: false
"""

    return f"""# Synthesized parametric CAP-CSP 5G cell ({config.preset})
[Global]
seed: {seed}
duration: {duration_s:.1f}
period: -1
multithreading: false
threads: 1
verbose: false
progress_log_period_s: 10

[UE]
ue_id: studyVqeg
ue_type: 1
n_ues: 1
n_antennas: 1
alpha_ul: 0.8
nominal_pusch_p0: -60
set_ul_pow: true
tx_power_ul: 23
cqi_period: 5
ri_period: 5
scaling_factor: 1
random_v: true
log_freq: 100
log_ue: true
log_quality: true
log_traffic: true
log_mobility: true
traffic_type: 0
ul_target: 0.500000
dl_target: 64.000000
var_perc: 0.050000
pkt_size: 12000
mobility_type: {mob_type}
pos_x: {config.study_distance_m:.6f}
pos_y: 0.000000
random_init: false
speed: {speed_kmh:.6f}
speed_var: {speed_var:.6f}
max_distance: 850.000000
time_target: 6.000000
time_target_var: 1.000000
priority: 1.000000
delta_metric: 1.0
delay_t_metric: 0.1
pkt_delay_budget: 0.500000
l4s_dual_queue: false
l4s_target_ms: 15
l4s_rtt_max_ms: 100
l4s_min_th_us: 800
l4s_range_us: 400
l4s_k: 2.0
l4s_classic_guard_ms: 1.0
ue_height: 1.5
ue_location_type: outdoor
building_penetration: none
{bg_section}
[Scenario]
scenario_type: 1
map_file: include/maps_scenarios/macroscopic_fading_map_URBAN_MACROCELL_3.5.json

[eNBConfig]
modulation_m: 1
target_ber: 0.00005
cqi_mode: 1
tx_power: 46.0
eNB_gain: 8.7
UT_gain: 0
power_boost: 2
frequency: 3500000000.0
bandwidth: {config.bandwidth_mhz * 1e6:.1f}

[PDCP_RLC]
backhaul_d: {config.backhaul_delay_ms / 1000.0:.6f}
backhaul_d_var: {config.backhaul_jitter_ms / 1000.0:.6f}
order_pkts: true

[MACLayer]
metric_type: 6
pf_alpha: 1.0
throughput_time_window_ms: 100.0
throughput_intra_tti_update: allocation_unit
log_freq: 50
log_mac: true
mimo_layers: 1
n_ofdm_syms: 14
n_re_freq: 12
numerology: 1
max_rtx_ul: 4
max_rtx_dl: 4
harq_model: legacy_bler
mcs_tables: true
scheduling_mode: 1
scheduling_type: 0
scheduling_config: 0
duplexing_type: 0
n_dl_slots: 7
n_ul_slots: 3
transition_c: 54
ratio_DL_UL: 0.5

[PHYLayer]
interference_ues: 2
interference_eNBs: 1
distance_interference: 3500
interfered_bandwidth_ratio: 0.1
thermal_noise: -174
enb_noise_figure: 2
ut_noise_figure: 9
air_delay_var_dl: 0.0
air_delay_var_ul: 0.0
rtx_period_ul: 0.004
rtx_period_var_ul: 0
rtx_proc_delay_ul: 0.002
rtx_proc_delay_var_ul: 0.0
rtx_period_dl: 0.005
rtx_period_var_dl: 0
rtx_proc_delay_dl: 0.002
rtx_proc_delay_var_dl: 0.0

{control_section}"""


def synthesize_parametric_cell(
    config: ParametricCellConfig,
    *,
    duration_s: float,
    seed: int,
    work_dir: Path,
) -> SynthesizedCell:
    """Write the effective `.ini` and `.ndjson` timeline for `config` into `work_dir`."""
    work_dir.mkdir(parents=True, exist_ok=True)
    horizon_s = max(float(duration_s) + 5.0, 10.0)
    horizon_tti = int(round(horizon_s * 1000.0))

    if config.load_rho <= 0.0 or config.bg_spatial == "none":
        lam_mean = 0.0
        n_pool = 0
        sessions: list[dict[str, Any]] = []
    else:
        positions, mean_share = _spatial_pool_and_mean_share(config)
        lam_mean = config.load_rho / mean_share
        peak_mult = (1.0 + config.burst_amplitude) if config.arrival_mode == "mmpp" else 1.0
        peak_lam = lam_mean * peak_mult
        n_pool = max(4, int(math.ceil(peak_lam + 4.5 * math.sqrt(peak_lam + 1.0) + 4)))
        rng = _seeded_rng(seed)
        sessions = _generate_sessions(
            config,
            lam_mean=lam_mean,
            n_pool=n_pool,
            positions=positions,
            duration_s=horizon_s,
            rng=rng,
        )

    by_tti = _build_study_mobility_events(config, duration_s=horizon_s)
    if config.study_dl_rmax_mbps is not None:
        by_tti.setdefault(0, []).append(
            {
                "target": "ue/studyVqeg",
                "set": {"dl.rmax_mbps": round(config.study_dl_rmax_mbps, 4)},
            }
        )
    if n_pool > 0:
        active_at_zero = {sess["slot"]: sess for sess in sessions if sess["start_tti"] == 0}
        for slot in range(n_pool):
            target = "ue/backgroundSfV" if n_pool == 1 else f"ue/backgroundSfV_{slot}"
            if slot in active_at_zero:
                s0 = active_at_zero[slot]
                by_tti.setdefault(0, []).append(
                    {
                        "target": target,
                        "set": {
                            "enabled": True,
                            "mobility.pos_x_m": round(s0["x_m"], 3),
                            "mobility.pos_y_m": round(s0["y_m"], 3),
                        },
                    }
                )
            else:
                by_tti.setdefault(0, []).append({"target": target, "set": {"enabled": False}})

        for sess in sessions:
            target = "ue/backgroundSfV" if n_pool == 1 else f"ue/backgroundSfV_{sess['slot']}"
            if 0 < sess["start_tti"] < horizon_tti:
                by_tti.setdefault(sess["start_tti"], []).append(
                    {
                        "target": target,
                        "set": {
                            "enabled": True,
                            "mobility.pos_x_m": round(sess["x_m"], 3),
                            "mobility.pos_y_m": round(sess["y_m"], 3),
                        },
                    }
                )
            if sess["end_tti"] < horizon_tti:
                by_tti.setdefault(sess["end_tti"], []).append(
                    {"target": target, "set": {"enabled": False}}
                )

    timeline_path: Path | None = None
    if by_tti:
        timeline_path = work_dir / "parametric-timeline.ndjson"
        lines = [
            json.dumps({"id": msg_id, "at_tti": tti, "cmds": by_tti[tti]}, separators=(",", ":"))
            for msg_id, tti in enumerate(sorted(by_tti), start=1)
        ]
        timeline_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    ini_path = work_dir / "parametric-base.ini"
    ini_path.write_text(
        _render_parametric_ini(
            config,
            duration_s=horizon_s,
            seed=seed,
            n_pool=n_pool,
            timeline_path=timeline_path,
        ),
        encoding="utf-8",
    )

    bg_iperf = {"backgroundSfV": config.bg_bitrate_mbps} if n_pool > 0 else {}
    return SynthesizedCell(
        ini_path=ini_path,
        timeline_path=timeline_path,
        background_iperf_ues=bg_iperf,
        pool_ue_count=n_pool,
        mean_active_bg_ues=round(lam_mean, 4),
        session_count=len(sessions),
    )

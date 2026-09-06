"""Bounded validation measurements and throttled hunt logs; no device input."""

import json
import time
from math import isfinite


class HuntDiagnostics:
    def __init__(self, log, *, clock=time.monotonic, interval=2.0):
        self.log = log
        self.clock = clock
        self.interval = interval
        self._last = {}

    def __call__(self, event, **fields):
        # Diagnostics must not interrupt an input-release path if a log sink fails.
        try:
            now = self.clock()
            if event in ("localization", "navigation_progress"):
                key = (event, fields.get("valid", True))
                if now - self._last.get(key, float("-inf")) < self.interval:
                    return
                self._last[key] = now
            self.log("[HUNT] " + json.dumps({"event": event, **fields},
                                           ensure_ascii=False, default=str))
        except Exception:
            pass


def stationary_localization(locate, wait, check_cancel, *, units_per_pixel,
                            tolerance_pixels=None, sample_count=10):
    """Measure stationary repeatability, not absolute position accuracy.

    Callbacks must be read-only (wait must not target enemies or move a camera).
    No tolerance is inferred from the measured noise or from camp radii.
    """
    if sample_count < 2 or not isfinite(units_per_pixel) or units_per_pixel <= 0:
        raise ValueError("Invalid stationary sample count or coordinate scale")
    if tolerance_pixels is not None and (not isfinite(tolerance_pixels) or tolerance_pixels <= 0):
        raise ValueError("Localization tolerance must be positive and finite")
    samples = []
    for index in range(sample_count):
        check_cancel()
        position = locate()
        if position is None:
            raise RuntimeError(f"Localization failed on stationary sample {index + 1}")
        if samples and (position.state_id, position.floor_id) != (samples[0].state_id, samples[0].floor_id):
            raise RuntimeError("Stationary samples changed map layer")
        samples.append(position)
        if index + 1 < sample_count:
            wait(0.5)
    spread = max(a.coordinate.distance_to(b.coordinate) for a in samples for b in samples)
    spread_pixels = spread / units_per_pixel
    return {
        "sample_count": len(samples),
        "state_id": samples[0].state_id,
        "floor_id": samples[0].floor_id,
        "samples_xy": [(s.coordinate.x, s.coordinate.y) for s in samples],
        "max_pairwise_spread_units": spread,
        "max_pairwise_spread_pixels": spread_pixels,
        "tolerance_pixels": tolerance_pixels,
        "within_tolerance": None if tolerance_pixels is None else spread_pixels <= tolerance_pixels,
        "absolute_error": None,
    }

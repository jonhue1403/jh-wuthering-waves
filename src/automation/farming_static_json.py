"""Strict, size-limited local JSON reader for read-only calibration audits.

Local evidence files are untrusted. Duplicate object members and JSON's
nonstandard NaN/Infinity literals are ambiguous; never treat them as a
well-formed calibration record. This module does not authorize any game input.
"""

import json


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate calibration JSON key")
        result[key] = value
    return result


def _reject_constant(_value):
    raise ValueError("Non-finite calibration JSON number")


def read_static_json(path, *, max_bytes):
    """Read exactly one bounded UTF-8 JSON object without duplicate keys.

    A second size check on the actual bytes prevents a file from growing
    between a caller's stat() check and the read. Paths and contents remain
    private; callers return path-free summary counts only.
    """
    if type(max_bytes) is not int or not 1 <= max_bytes <= 1024 * 1024:
        raise ValueError("Invalid calibration JSON byte limit")
    with path.open("rb") as stream:
        raw = stream.read(max_bytes + 1)
    if not raw or len(raw) > max_bytes:
        raise ValueError("Empty or oversized calibration JSON")
    data = json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=_unique_pairs,
        parse_constant=_reject_constant,
    )
    if not isinstance(data, dict):
        raise ValueError("Calibration metadata must be a JSON object")
    return data

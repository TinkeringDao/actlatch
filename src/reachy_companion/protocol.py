"""Proposed bridge envelope validation. Does not authenticate or dispatch actions."""

from __future__ import annotations

import math
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

VERSION = "reachy-companion/0.1"


@dataclass(frozen=True)
class Envelope:
    session_id: str
    generation_id: int
    request_id: str
    message_type: str
    payload: Mapping[str, Any]

    @classmethod
    def parse(cls, data: dict, *, now: float | None = None) -> Envelope:
        if not isinstance(data, dict) or set(data) != {
            "protocol_version",
            "session_id",
            "generation_id",
            "request_id",
            "message_type",
            "timestamp",
            "expires_at",
            "payload",
        }:
            raise ValueError("unknown or missing envelope field")
        if data["protocol_version"] != VERSION:
            raise ValueError("unsupported protocol version")
        for key in ("session_id", "request_id"):
            if not isinstance(data[key], str) or not re.fullmatch(
                r"[A-Za-z0-9_-]{8,80}", data[key]
            ):
                raise ValueError("invalid identifier")
        generation = data["generation_id"]
        if type(generation) is not int or not 0 <= generation <= 2**31 - 1:
            raise ValueError("invalid generation")
        current = time.time() if now is None else now
        for value in (current, data["timestamp"], data["expires_at"]):
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError("invalid timestamp")
        issued, expiry = data["timestamp"], data["expires_at"]
        if not issued <= current + 2 or not current < expiry or not 0 < expiry - issued <= 60:
            raise ValueError("expired or invalid envelope lifetime")
        kind, payload = data["message_type"], data["payload"]
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
        if kind == "session.stop":
            valid = payload == {}
        elif kind == "activity.select":
            valid = set(payload) == {"activity_id"} and isinstance(payload["activity_id"], str)
            valid = valid and bool(re.fullmatch(r"[a-z][a-z0-9_]{1,63}", payload["activity_id"]))
        else:
            raise ValueError("message type has no implemented scaffold handler")
        if not valid:
            raise ValueError("invalid payload")
        return cls(
            data["session_id"],
            generation,
            data["request_id"],
            kind,
            MappingProxyType(dict(payload)),
        )

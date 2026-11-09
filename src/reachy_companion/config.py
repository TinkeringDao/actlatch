"""Strict scaffold configuration; address checks are not network containment."""

from __future__ import annotations

import ipaddress
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

_NETWORKS = tuple(
    ipaddress.ip_network(x)
    for x in ("127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "::1/128", "fc00::/7")
)


def local_url(value: object) -> str:
    """Accept literal LAN/loopback URLs only; no DNS lookup or HTTP request occurs."""
    if not isinstance(value, str) or any(c.isspace() for c in value):
        raise ValueError("service URL must be a string without whitespace")
    try:
        url = urlsplit(value)
        address = ipaddress.ip_address(url.hostname or "")
        port = url.port
    except ValueError as exc:
        raise ValueError("service URL requires a literal local IP and valid port") from exc
    if (
        url.scheme not in {"http", "https"}
        or url.username is not None
        or url.password is not None
        or url.query
        or url.fragment
        or (port is not None and port == 0)
        or not any(address.version == net.version and address in net for net in _NETWORKS)
    ):
        raise ValueError("service URL must be local and contain no credentials/query/fragment")
    return value


@dataclass(frozen=True)
class Config:
    mode: str
    language: str
    model_url: str
    asr_url: str
    tts_url: str

    @classmethod
    def load(cls, path: str | Path) -> Config:
        with Path(path).open("rb") as stream:
            data = tomllib.load(stream)
        if set(data) != {"runtime", "services"}:
            raise ValueError("configuration requires only runtime and services sections")
        runtime, services = data["runtime"], data["services"]
        if not isinstance(runtime, dict) or not isinstance(services, dict):
            raise ValueError("configuration sections must be tables")
        if set(runtime) != {
            "mode",
            "language",
            "hardware_enabled",
            "cloud_fallback",
            "raw_media_retention",
        } or set(services) != {"model_url", "asr_url", "tts_url"}:
            raise ValueError("unknown or missing configuration field")
        if runtime["mode"] != "simulation" or runtime["language"] != "de-DE":
            raise ValueError("this scaffold supports German simulation only")
        for key in ("hardware_enabled", "cloud_fallback", "raw_media_retention"):
            if runtime[key] is not False:
                raise ValueError(f"{key} must be false in the scaffold")
        return cls(
            "simulation",
            "de-DE",
            *(local_url(services[k]) for k in ("model_url", "asr_url", "tts_url")),
        )

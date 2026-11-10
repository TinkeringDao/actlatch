#!/usr/bin/env python3
"""Explicit maintainer command: refresh selected PUBLIC evidence, never robot data."""

from __future__ import annotations

import ast
import hashlib
import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "ReachyCompanionSourceAudit"})
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.read()


def main() -> int:
    results = []
    for repo in ("reachy_mini", "reachy_mini_conversation_app"):
        url = f"https://api.github.com/repos/pollen-robotics/{repo}/releases/latest"
        data = json.loads(fetch(url))
        results.append(
            {
                "kind": "latest_release",
                "url": url,
                "observed": {
                    key: data.get(key) for key in ("tag_name", "published_at", "html_url")
                },
            }
        )
    for repo, kind, number in (
        ("reachy_mini_conversation_app", "pulls", 514),
        ("reachy_mini_conversation_app", "pulls", 515),
        ("reachy_mini", "issues", 1494),
        ("reachy_mini", "issues", 1462),
        ("reachy_mini", "issues", 1523),
        ("reachy_mini", "pulls", 1533),
    ):
        url = f"https://api.github.com/repos/pollen-robotics/{repo}/{kind}/{number}"
        data = json.loads(fetch(url))
        results.append(
            {
                "kind": kind,
                "url": url,
                "observed": {
                    key: data.get(key)
                    for key in ("title", "state", "merged_at", "updated_at", "html_url")
                },
            }
        )
    raw_root = "https://raw.githubusercontent.com/pollen-robotics/"
    url = raw_root + "reachy_mini/v1.13.0/src/reachy_mini/reachy_mini.py"
    source = fetch(url)
    tree = ast.parse(source)
    robot = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ReachyMini")
    init = next(n for n in robot.body if isinstance(n, ast.FunctionDef) and n.name == "__init__")
    default_nodes = {
        arg.arg: value
        for arg, value in zip(
            init.args.args[-len(init.args.defaults) :], init.args.defaults, strict=True
        )
    }
    automatic_body_yaw_default = ast.literal_eval(default_nodes["automatic_body_yaw"])
    calls = {
        n.func.attr
        for n in ast.walk(init)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
    }
    results.append(
        {
            "kind": "pinned_sdk_source",
            "url": url,
            "sha256": hashlib.sha256(source).hexdigest(),
            "observed": {
                "automatic_body_yaw_default": automatic_body_yaw_default,
                "sets_automatic_body_yaw": "set_automatic_body_yaw" in calls,
                "configures_media": "_configure_mediamanager" in calls,
            },
        }
    )
    for suffix, observations in (
        (
            "reachy_mini/v1.13.0/docs/source/SDK/telemetry.md",
            {
                "telemetry_on_by_default": "**on by default**",
                "opt_out_documented": "DO_NOT_TRACK=1",
            },
        ),
        (
            "reachy_mini_conversation_app/v1.1.1/README.md",
            {
                "hosted_default_documented": "default setup uses the Hugging Face backend",
                "local_backend_documented": "HF_REALTIME_WS_URL",
            },
        ),
    ):
        url = raw_root + suffix
        body = fetch(url)
        results.append(
            {
                "kind": "pinned_documentation",
                "url": url,
                "sha256": hashlib.sha256(body).hexdigest(),
                "observed": {key: needle in body.decode() for key, needle in observations.items()},
            }
        )
    report = {
        "checked_at": datetime.now(UTC).isoformat(),
        "scope": "Selected consequential upstream claims, not every source or hardware behavior",
        "robot_tests": False,
        "results": results,
    }
    path = ROOT / "docs/research/source-checks.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Recorded {len(results)} public-source checks in docs/research/source-checks.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

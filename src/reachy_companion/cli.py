"""Offline scaffold entry points. Commands never instantiate a robot SDK."""

from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from .activities import ActivitySession, load_catalog
from .config import Config


def doctor(config: Config) -> dict:
    return {
        "configuration_valid": True,
        "mode": config.mode,
        "language": config.language,
        "network_containment_verified": False,
        "live_adapters_implemented": False,
        "ready_for_child_use": False,
        "proxy_environment_present": any(
            key.lower() in {"http_proxy", "https_proxy", "all_proxy"} for key in os.environ
        ),
        "commissioning_required": [
            "physical mute/stop and media buffering",
            "local German ASR/model/TTS benchmark",
            "child gateway permissions",
            "all-hop egress and retention verification",
        ],
    }


class HealthHandler(BaseHTTPRequestHandler):
    """Read-only loopback development health endpoint. No command/control API."""

    def do_GET(self) -> None:
        if self.path != "/healthz":
            self.send_error(404)
            return
        body = json.dumps({"status": "scaffold_alive", "ready_for_child_use": False}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/dev.toml"))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")
    demo = sub.add_parser("demo", help="Print synthetic German prompts; no microphone or model")
    demo.add_argument("--catalog", type=Path, default=Path("content/activities.json"))
    demo.add_argument("--activity", default="story_turns")
    serve = sub.add_parser("serve", help="Development health endpoint, loopback only")
    serve.add_argument("--port", type=int, default=8099)
    args = parser.parse_args(argv)
    try:
        config = Config.load(args.config)
        if args.command == "doctor":
            print(json.dumps(doctor(config), indent=2))
        elif args.command == "demo":
            catalog = load_catalog(args.catalog)
            if args.activity not in catalog:
                raise ValueError("unknown activity")
            session = ActivitySession(catalog[args.activity], simulation=True)
            print("SIMULATION · German text prompts only · no learner data stored")
            while turn := session.next_prompt():
                print(turn.text_de)
            session.stop()
        else:
            if not 0 <= args.port <= 65535:
                raise ValueError("invalid port")
            with HTTPServer(("127.0.0.1", args.port), HealthHandler) as server:
                print(
                    f"Development health: http://127.0.0.1:{server.server_port}/healthz", flush=True
                )
                server.serve_forever()
        return 0
    except (ValueError, OSError, TypeError) as exc:
        print(f"Configuration/operation error: {exc}")
        return 2
    except KeyboardInterrupt:
        return 0

# actlatch

[![CI](https://github.com/TinkeringDao/actlatch/actions/workflows/ci.yml/badge.svg)](https://github.com/TinkeringDao/actlatch/actions/workflows/ci.yml)
[![Security](https://github.com/TinkeringDao/actlatch/actions/workflows/security.yml/badge.svg)](https://github.com/TinkeringDao/actlatch/actions/workflows/security.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Fail-closed SQLite actuator fault-latch recovery controller, offline simulation scaffold, and commissioning safety checklist for **Reachy Mini Wireless**.

The runnable Python package exercises local-only endpoint validation, message-envelope parsing, generation-gated German activity templates, and SQLite-backed fault/retry budgets without touching network sockets, microphones, cameras, or robot actuators.

## Current Scope & Limitations

- Simulation only (`ready_for_child_use: false`). Live ASR, TTS, local model inference, WebRTC/SDK robot media, and authenticated caregiver controls remain unconnected adapter seams documented in [`docs/adapters.md`](docs/adapters.md). Importing or running `reachy-companion` opens zero network sockets and constructs no robot SDK client.
- Unreviewed fixture catalog. All four German activity templates in [`content/activities.json`](content/activities.json) ship with `parent_reviewed: false`; non-simulation `ActivitySession` calls reject unreviewed entries with `PermissionError`.
- Policy vs. hardware actuation. `RecoveryController` (`src/reachy_companion/recovery.py`) atomically reserves retry attempts in SQLite, enforces cooldowns and persistent incident caps across restarts, and latches `hardware`, `privacy`, and `identity` faults until a verified reset, while stopping physical audio or motion remains the caller's responsibility during commissioning.

## Quickstart

Requires Python 3.11+ and [`uv`](https://docs.astral.sh/uv/):

```sh
git clone https://github.com/TinkeringDao/actlatch.git
cd actlatch
uv sync --locked
uv run reachy-companion doctor
uv run reachy-companion demo --activity story_turns
uv run reachy-companion serve --port 8099
```

`serve` binds a read-only health endpoint on `http://127.0.0.1:8099/healthz` (`POST` control routes return `501`).

## Architecture & Docs

```
Wireless robot edge -> Local German ASR/TTS -> Isolated local dialog gateway
  -> Curated activity coordinator -> Scoped local learner store
```

- [`docs/architecture.md`](docs/architecture.md): system boundaries, SDK v1.13.0 constructor side effects (`automatic_body_yaw=True`), and local processing constraints.
- [`docs/adapters.md`](docs/adapters.md): adapter contracts and protocol differences across SDK WebSocket, WebRTC, and realtime voice streams.
- [`docs/commissioning.md`](docs/commissioning.md): pre-deployment hardware, stop-latency, audio tail, egress, and backup-deletion checklist.
- [`docs/learning.md`](docs/learning.md) & [`personas/reachy-play-guide.md`](personas/reachy-play-guide.md): German preschool guided-play design and dialog persona rules.
- [`knowledge/`](knowledge/): 107 reviewed upstream source URLs, 17 ecosystem project notes, and 37 read-only troubleshooting runbooks, plus [`scripts/reaudit_sources.py`](scripts/reaudit_sources.py) to refresh [`docs/research/source-checks.json`](docs/research/source-checks.json).

## Local Checks

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv build
```

Keep local overrides in gitignored `configs/local.toml` and runtime SQLite files in gitignored `.state/`. Never commit credentials, learner records, household transcripts, raw audio/video, or model weights.

## License & Legal

Licensed under the [MIT License](LICENSE); upstream SDKs, models, and voices retain their own terms.
Independent, non-commercial open-source project not affiliated with Pollen Robotics or Hugging Face, Inc. (see [`LEGAL.md`](LEGAL.md) and [`SECURITY.md`](SECURITY.md)).

# Scaffold validation

Local validation on 3 November 2026 used synthetic inputs only.

| Check | Observed result |
|---|---|
| Python 3.12.13: `uv run pytest -q` | 86 passed |
| Python 3.11: `uv run --isolated --python 3.11 pytest -q` | 86 passed |
| `uv run ruff check .` | Passed |
| `uv run ruff format --check .` | Passed |
| `uv build` | Source distribution and wheel built |
| CLI doctor/demo | Configuration accepted; German text printed; child readiness false |
| `docker compose config --quiet` | Compose syntax accepted |
| Container build | Built local `reachy-companion:scaffold` image |
| Container health smoke | HTTP 200 with `scaffold_alive`, child readiness false |
| Container restrictions inspected | Network `none`, read-only root, UID/GID 10001, capabilities dropped |

The container was stopped after its smoke test. This is not a persistent
deployment. The GitHub workflow repeats the Python/lint/build checks when pushed;
its presence alone is not a successful remote CI result.

The tests specifically exercise recovery persistence across new controllers and
caller labels, exhaustion beyond rate-window expiry, authenticated-decision flag
validation, verified reset without erasing rate history or other latches,
clock/store failures, atomic reservations, cancellation, content gating and
offline behavior. A loopback HTTP test confirms the health service has no POST
control route. This does not establish physical motor/audio stop, microphone
privacy, child speech recognition quality, learning outcomes, real adapter
authorization or network containment of the proposed complete system.

"""Synthetic state, boundary and interruption tests; no child or robot input."""

import json
import socket
import threading
from http.client import HTTPConnection
from http.server import HTTPServer
from pathlib import Path

import pytest

from reachy_companion.activities import ActivitySession, SpeechTurn, load_catalog
from reachy_companion.cli import HealthHandler, doctor, main
from reachy_companion.config import Config, local_url
from reachy_companion.protocol import Envelope

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "url",
    [
        "https://api.example.com/v1",
        "http://8.8.8.8",
        "http://203.0.113.1",
        "http://localhost",
        "http://127.0.0.1.evil.example",
        "http://user:secret@127.0.0.1",
        "http://127.0.0.1?token=secret",
        "http://127.0.0.1#fragment",
        "file:///tmp/data",
        "http://[::ffff:8.8.8.8]",
        "http://127.0.0.1:0",
        "http://127.0.0.1:99999",
        None,
    ],
)
def test_nonlocal_or_ambiguous_service_routes_rejected(url):
    with pytest.raises(ValueError):
        local_url(url)


def test_config_fields_do_not_depend_on_toml_order(tmp_path):
    original = (ROOT / "configs/dev.toml").read_text()
    reordered = (
        original.replace('model_url = "http://127.0.0.1:1234/v1"\n', "")
        + '\nmodel_url = "http://127.0.0.1:1234/v1"\n'
    )
    p = tmp_path / "config.toml"
    p.write_text(reordered)
    assert Config.load(p).model_url == "http://127.0.0.1:1234/v1"


@pytest.mark.parametrize("setting", ["hardware_enabled", "cloud_fallback", "raw_media_retention"])
def test_unsafe_runtime_modes_cannot_be_enabled_in_scaffold(tmp_path, setting):
    data = (
        (ROOT / "configs/dev.toml").read_text().replace(f"{setting} = false", f"{setting} = true")
    )
    p = tmp_path / "config.toml"
    p.write_text(data)
    with pytest.raises(ValueError):
        Config.load(p)


def test_unreviewed_content_denied_for_child_and_explicit_simulation_works():
    activities = load_catalog(ROOT / "content/activities.json")
    assert len(activities) == 4
    assert all(not item.parent_reviewed for item in activities.values())
    activity = activities["story_turns"]
    with pytest.raises(PermissionError):
        ActivitySession(activity)
    session = ActivitySession(activity, simulation=True)
    old = session.next_prompt()
    assert session.accepts(old)
    session.stop()
    assert not session.accepts(old)
    assert session.next_prompt() is None
    assert not session.accepts(SpeechTurn("another-session", session.generation, "synthetic"))


def envelope():
    return {
        "protocol_version": "reachy-companion/0.1",
        "session_id": "synthetic_session",
        "generation_id": 0,
        "request_id": "synthetic_request",
        "message_type": "activity.select",
        "timestamp": 1000,
        "expires_at": 1030,
        "payload": {"activity_id": "story_turns"},
    }


@pytest.mark.parametrize(
    "patch",
    [
        {"protocol_version": "future/2"},
        {"generation_id": True},
        {"generation_id": -1},
        {"expires_at": 999},
        {"expires_at": 1100},
        {"timestamp": float("nan")},
        {"timestamp": 1100},
        {"command": "shell"},
        {"message_type": "robot.move"},
        {"payload": {"activity_id": "story_turns", "bank": "adult"}},
        {"payload": {"activity_id": "../../private"}},
    ],
)
def test_untrusted_envelopes_cannot_expand_scope_or_replay_expired_output(patch):
    with pytest.raises(ValueError):
        Envelope.parse(envelope() | patch, now=1000)


def test_envelope_payload_is_immutable_and_detached():
    data = envelope()
    parsed = Envelope.parse(data, now=1000)
    data["payload"]["activity_id"] = "drawing_chat"
    assert parsed.payload["activity_id"] == "story_turns"
    with pytest.raises(TypeError):
        parsed.payload["activity_id"] = "drawing_chat"


def test_doctor_and_demo_are_offline_and_store_no_data(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def network_forbidden(*args, **kwargs):
        raise AssertionError("offline command attempted a socket connection")

    monkeypatch.setattr(socket.socket, "connect", network_forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", network_forbidden)
    config = Config.load(ROOT / "configs/dev.toml")
    assert doctor(config)["ready_for_child_use"] is False
    assert doctor(config)["network_containment_verified"] is False
    assert (
        main(
            [
                "--config",
                str(ROOT / "configs/dev.toml"),
                "demo",
                "--catalog",
                str(ROOT / "content/activities.json"),
            ]
        )
        == 0
    )
    assert "SIMULATION" in capsys.readouterr().out
    assert not list(tmp_path.iterdir())


def test_health_is_alive_but_not_child_ready_and_has_no_control_api():
    server = HTTPServer(("127.0.0.1", 0), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=2)
    try:
        connection.request("GET", "/healthz")
        response = connection.getresponse()
        assert response.status == 200
        assert json.loads(response.read()) == {
            "status": "scaffold_alive",
            "ready_for_child_use": False,
        }
        connection.request("POST", "/activity.select", body=b"{}")
        response = connection.getresponse()
        assert response.status == 501
        response.read()
    finally:
        connection.close()
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def test_catalog_rejects_unknown_raw_data_fields(tmp_path):
    data = json.loads((ROOT / "content/activities.json").read_text())
    data["activities"][0]["raw_transcript"] = "synthetic"
    p = tmp_path / "catalog.json"
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_catalog(p)

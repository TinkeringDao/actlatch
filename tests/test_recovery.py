"""Synthetic recovery-policy checks; no network or physical adapters are used."""

import dataclasses
import sqlite3

import pytest

from reachy_companion.recovery import RecoveryController


class FakeClock:
    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def test_allow_reserves_and_decisions_are_immutable(tmp_path):
    clock = FakeClock()
    with RecoveryController(tmp_path / "policy.sqlite", clock) as policy:
        decision = policy.allow("transport_reconnect")
        assert decision.allowed
        with pytest.raises(dataclasses.FrozenInstanceError):
            decision.allowed = False
        assert policy.allow("transport_reconnect").reason == "cooldown"


def test_budget_survives_new_controllers_sessions_and_incidents(tmp_path):
    clock = FakeClock()
    path = tmp_path / "policy.sqlite"
    for attempt in range(3):
        with RecoveryController(path, clock) as policy:
            assert policy.allow(
                "transport_reconnect",
                incident_id=f"incident-{attempt}",
                session_id=f"session-{attempt}",
            ).allowed
        clock.advance(10)
    with RecoveryController(path, clock) as policy:
        decision = policy.allow(
            "transport_reconnect", incident_id="brand-new", session_id="another-session"
        )
        assert not decision.allowed
        assert decision.reason == "incident_attempt_limit"
        assert decision.retry_after_seconds == 0
    clock.advance(10000)
    with RecoveryController(path, clock) as policy:
        assert policy.allow("transport_reconnect").reason == "budget_exhausted"
        assert policy.allow("cached_play").reason == "budget_exhausted"
        assert policy.allow("stop").allowed


def test_fault_label_switch_cannot_replenish_action_budget(tmp_path):
    clock = FakeClock()
    with RecoveryController(tmp_path / "policy.sqlite", clock) as policy:
        for fault in ["transport", "provider", "transport"]:
            assert policy.allow("transport_reconnect", fault=fault).allowed
            clock.advance(10)
        assert (
            policy.allow("transport_reconnect", fault="provider").reason == "incident_attempt_limit"
        )


def test_cooldown_boundary_and_no_automatic_replenishment(tmp_path):
    clock = FakeClock()
    with RecoveryController(tmp_path / "policy.sqlite", clock) as policy:
        assert policy.allow("cached_play", fault="none").allowed
        clock.advance(1)
        decision = policy.allow("cached_play", fault="none")
        assert decision.reason == "cooldown"
        assert decision.retry_after_seconds == 1
        clock.advance(1)
        assert policy.allow("cached_play", fault="none").allowed
        clock.advance(2)
        assert policy.allow("cached_play", fault="none").allowed
        clock.advance(2)
        assert policy.allow("cached_play", fault="none").reason == "incident_attempt_limit"
        clock.now = 1060
        assert policy.allow("cached_play", fault="none").reason == "budget_exhausted"
        assert policy.reset_budget(
            "cached_play", authorized=True, postcondition_verified=True
        ).allowed
        assert policy.allow("cached_play", fault="none").allowed


@pytest.mark.parametrize(
    ("authorized", "verified"),
    [(False, False), (True, False), (False, True), (1, True), (True, "yes")],
)
def test_budget_reset_consumes_both_trusted_decisions(tmp_path, authorized, verified):
    clock = FakeClock()
    with RecoveryController(tmp_path / "policy.sqlite", clock) as policy:
        for _ in range(3):
            assert policy.allow("cached_play").allowed
            clock.advance(2)
        assert policy.allow("cached_play").reason == "incident_attempt_limit"
        assert (
            policy.reset_budget(
                "cached_play", authorized=authorized, postcondition_verified=verified
            ).reason
            == "verified_parent_recovery_required"
        )
        clock.advance(10000)
        assert policy.allow("cached_play").reason == "budget_exhausted"


def test_verified_reset_preserves_rate_history_and_physical_latches(tmp_path):
    clock = FakeClock()
    with RecoveryController(tmp_path / "policy.sqlite", clock) as policy:
        assert policy.allow("cached_play").allowed
        policy.latch("privacy")
        assert policy.reset_budget(
            "cached_play", authorized=True, postcondition_verified=True
        ).allowed
        assert policy.allow("cached_play").reason == "latch_privacy"
        policy.clear_latch("privacy", authorized=True)
        assert policy.allow("cached_play").reason == "cooldown"
        for _ in range(2):
            clock.advance(2)
            assert policy.allow("cached_play").allowed
        assert policy.reset_budget(
            "cached_play", authorized=True, postcondition_verified=True
        ).allowed
        clock.advance(2)
        assert policy.allow("cached_play").reason == "action_attempt_limit"
        clock.advance(10000)
        assert policy.allow("transport_read").reason == "budget_exhausted"


def test_restart_requires_owned_and_idle_context(tmp_path):
    with RecoveryController(tmp_path / "policy.sqlite", FakeClock()) as policy:
        assert policy.allow("adapter_restart").reason == "adapter_not_owned"
        assert policy.allow("adapter_restart", adapter_owned=True).reason == "adapter_not_idle"
        assert policy.allow("adapter_restart", adapter_owned=True, adapter_idle=True).allowed


def test_global_restart_limit_persists_across_faults_and_local_windows(tmp_path):
    clock = FakeClock()
    path = tmp_path / "policy.sqlite"
    kwargs = {"adapter_owned": True, "adapter_idle": True}
    with RecoveryController(path, clock) as policy:
        assert policy.allow("adapter_restart", **kwargs).allowed
    clock.advance(121)
    with RecoveryController(path, clock) as policy:
        assert policy.reset_budget(
            "adapter_restart", authorized=True, postcondition_verified=True
        ).allowed
        assert policy.allow("adapter_restart", fault="provider", **kwargs).allowed
    clock.advance(121)
    with RecoveryController(path, clock) as policy:
        assert policy.reset_budget(
            "adapter_restart", authorized=True, postcondition_verified=True
        ).allowed
        decision = policy.allow("adapter_restart", incident_id="new", **kwargs)
        assert decision.reason == "global_adapter_restart_limit"
        assert decision.retry_after_seconds == 358
    clock.now = 1600
    with RecoveryController(path, clock) as policy:
        assert policy.allow("adapter_restart", **kwargs).reason == "budget_exhausted"
        assert policy.reset_budget(
            "adapter_restart", authorized=True, postcondition_verified=True
        ).allowed
        assert policy.allow("adapter_restart", **kwargs).allowed


@pytest.mark.parametrize("fault", ["hardware", "privacy", "unknown_identity"])
def test_latch_veto_persists_and_wins_over_cooldown(tmp_path, fault):
    clock = FakeClock()
    path = tmp_path / "policy.sqlite"
    with RecoveryController(path, clock) as policy:
        assert policy.allow("cached_play").allowed
        policy.latch(fault)
    with RecoveryController(path, clock) as policy:
        assert policy.latches() == (fault,)
        assert policy.allow("cached_play").reason == f"latch_{fault}"
        assert policy.allow("transport_reconnect").reason == f"latch_{fault}"
        assert (
            policy.allow("adapter_restart", adapter_owned=True, adapter_idle=True).reason
            == f"latch_{fault}"
        )


def test_hardware_fault_observation_creates_latch_and_priority_is_deterministic(tmp_path):
    with RecoveryController(tmp_path / "policy.sqlite", FakeClock()) as policy:
        assert policy.allow("cached_play", fault="privacy").reason == "latch_privacy"
        assert policy.allow("transport_read", fault="hardware").reason == "latch_hardware"
        policy.latch("unknown_identity")
        assert policy.latches() == ("hardware", "privacy", "unknown_identity")
        assert policy.allow("cached_play").reason == "latch_hardware"


@pytest.mark.parametrize("authorization", [False, None, 1, "yes", "true"])
def test_clear_requires_explicit_trusted_authorization(tmp_path, authorization):
    with RecoveryController(tmp_path / "policy.sqlite", FakeClock()) as policy:
        policy.latch("privacy")
        assert (
            policy.clear_latch("privacy", authorized=authorization).reason
            == "parent_authorization_required"
        )
        assert policy.latches() == ("privacy",)


def test_authorized_clear_does_not_reset_budgets_or_other_latches(tmp_path):
    clock = FakeClock()
    with RecoveryController(tmp_path / "policy.sqlite", clock) as policy:
        for _ in range(3):
            assert policy.allow("transport_reconnect").allowed
            clock.advance(10)
        policy.latch("hardware")
        policy.latch("privacy")
        assert policy.clear_latch("hardware", authorized=True).allowed
        assert policy.allow("transport_reconnect").reason == "latch_privacy"
        assert policy.clear_latch("privacy", authorized=True).allowed
        assert policy.allow("transport_reconnect").reason == "incident_attempt_limit"


def test_ordinary_child_stop_is_not_a_fault_latch_or_auto_recovery_trigger(tmp_path):
    with RecoveryController(tmp_path / "policy.sqlite", FakeClock()) as policy:
        assert policy.allow("child_stop").allowed
        assert policy.allow("stop", fault="child_stop").allowed
        assert policy.latches() == ()
        assert policy.allow("adapter_restart", fault="child_stop").reason == "fault_not_recoverable"
        assert policy.allow("cached_play", fault="none").allowed


@pytest.mark.parametrize("action", ["stop", "invalidate_output", "child_stop"])
def test_stop_does_not_depend_on_latches_store_or_clock(tmp_path, action):
    clock = FakeClock()
    policy = RecoveryController(tmp_path / "policy.sqlite", clock)
    policy.latch("hardware")
    clock.now = float("nan")
    policy.close()
    assert policy.allow(action, fault=object(), incident_id=object()).allowed
    assert policy.allow("cached_play").reason == "store_unavailable"


@pytest.mark.parametrize("bad", [None, [], {}, 5, "firmware_update", "reboot_robot"])
def test_unknown_actions_fail_closed(tmp_path, bad):
    with RecoveryController(tmp_path / "policy.sqlite", FakeClock()) as policy:
        assert policy.allow(bad).reason == "unknown_action"


@pytest.mark.parametrize("bad", [None, [], {}, 5, "magic_fault", "child said something private"])
def test_unknown_faults_fail_closed_without_logging_payload(tmp_path, bad):
    path = tmp_path / "policy.sqlite"
    with RecoveryController(path, FakeClock()) as policy:
        assert policy.allow("cached_play", fault=bad).reason == "unknown_fault"
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM recovery_events").fetchone()[0] == 0


@pytest.mark.parametrize("bad", ["", "spaces are not an ID", "ä", "x" * 129, [], 1])
def test_invalid_labels_and_untrusted_boolean_values_fail_closed(tmp_path, bad):
    with RecoveryController(tmp_path / "policy.sqlite", FakeClock()) as policy:
        assert policy.allow("cached_play", incident_id=bad).reason == "invalid_input"
        assert policy.allow("cached_play", adapter_owned=1).reason == "invalid_input"


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1, True, "1000", None])
def test_invalid_clock_never_grants_attempt(tmp_path, bad):
    with RecoveryController(tmp_path / "policy.sqlite", FakeClock(bad)) as policy:
        assert policy.allow("cached_play").reason == "invalid_clock"
        assert policy.allow("stop").allowed


def test_clock_rollback_survives_process_restart_and_clear(tmp_path):
    path = tmp_path / "policy.sqlite"
    clock = FakeClock()
    with RecoveryController(path, clock) as policy:
        assert policy.allow("transport_reconnect").allowed
    clock.now = 500
    with RecoveryController(path, clock) as policy:
        assert policy.allow("transport_reconnect").reason == "clock_rollback"
        policy.latch("privacy")
        assert policy.allow("cached_play").reason == "latch_privacy"
        policy.clear_latch("privacy", authorized=True)
        assert policy.allow("cached_play").reason == "clock_rollback"
    clock.now = 1010
    with RecoveryController(path, clock) as policy:
        assert policy.allow("transport_reconnect").allowed


def test_labels_do_not_enter_persistent_store(tmp_path):
    path = tmp_path / "policy.sqlite"
    with RecoveryController(path, FakeClock()) as policy:
        assert policy.record(
            "transport_read", session_id="SYNTHETIC_SESSION", incident_id="SYNTHETIC_INCIDENT"
        ).allowed
    with sqlite3.connect(path) as db:
        dump = "\n".join(db.iterdump())
    assert "SYNTHETIC_SESSION" not in dump
    assert "SYNTHETIC_INCIDENT" not in dump


def test_two_connections_cannot_double_spend_cooldown(tmp_path):
    path = tmp_path / "policy.sqlite"
    clock = FakeClock()
    with RecoveryController(path, clock) as first, RecoveryController(path, clock) as second:
        assert first.decide("transport_reconnect").allowed
        assert second.decide("transport_reconnect").reason == "cooldown"

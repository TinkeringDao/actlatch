"""Persistent, deterministic recovery decisions; this module executes no recovery.

``allow`` atomically reserves an attempt when it returns an allowed decision.
``decide`` and ``record`` are aliases for that same operation, not dry-run checks
or an arbitrary text-logging API. The caller must execute at most one approved
operation per reservation. Session and incident labels are deliberately neither
persisted nor budget keys: changing them cannot replenish attempts.

The store retains only fixed action/fault/reason codes and timestamps. It is not
an encrypted child-memory store. Fault classification, adapter ownership, idle
state and parent authentication must be established by a trusted caller. In
particular, ``clear_latch(..., authorized=True)`` consumes an authorization result;
the boolean itself is not an authentication mechanism.

Stop/output invalidation decisions are independent of storage and clock health.
The caller remains responsible for actually stopping output. An ordinary child
stop is not a persistent fault; it must still invalidate the current output
generation in the separate interaction controller.
"""

from __future__ import annotations

import math
import sqlite3
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType


@dataclass(frozen=True)
class RecoveryDecision:
    """A policy result, never evidence that a physical operation succeeded."""

    allowed: bool
    reason: str
    retry_after_seconds: float = 0.0


@dataclass(frozen=True)
class RecoveryPolicy:
    max_attempts: int
    window_seconds: float
    cooldown_seconds: float


POLICIES = MappingProxyType(
    {
        "transport_read": RecoveryPolicy(5, 60.0, 1.0),
        "transport_reconnect": RecoveryPolicy(3, 300.0, 10.0),
        "cached_play": RecoveryPolicy(3, 60.0, 2.0),
        "adapter_restart": RecoveryPolicy(1, 120.0, 60.0),
    }
)
GLOBAL_ADAPTER_RESTART_LIMIT = 2
GLOBAL_ADAPTER_RESTART_WINDOW_SECONDS = 600.0
LATCH_PRIORITY = ("hardware", "privacy", "unknown_identity")
KNOWN_FAULTS = frozenset({"none", "transport", "provider", "child_stop", *LATCH_PRIORITY})
INDEPENDENT_ACTIONS = frozenset({"stop", "invalidate_output", "child_stop"})
_MAX_EVENTS = 256


class RecoveryController:
    """Reserve narrow recovery attempts with budgets/latches surviving restarts.

    Incident budgets persist without time-based replenishment. Exhaustion
    latches all recovery until verified parent reset. Rate windows additionally
    constrain each action across fault classes. Adapter restarts also have a
    longer global window. They require
    explicit ``adapter_idle=True`` and ``adapter_owned=True`` context. None of
    these controls constructs an SDK, moves motors, starts playback, or performs
    a network request.
    """

    def __init__(self, store_path: str | Path, clock: Callable[[], float] = time.time) -> None:
        if not callable(clock):
            raise TypeError("clock must be callable")
        if not isinstance(store_path, (str, Path)) or not str(store_path):
            raise ValueError("store_path must be a nonempty local SQLite path")
        self._clock = clock
        self._lock = threading.RLock()
        self._closed = False
        if str(store_path) != ":memory:":
            Path(store_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(
            str(store_path), timeout=5.0, isolation_level=None, check_same_thread=False
        )
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS recovery_meta (
                key TEXT PRIMARY KEY,
                value REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS recovery_latches (
                fault TEXT PRIMARY KEY
            );
            CREATE TABLE IF NOT EXISTS recovery_budgets (
                action TEXT PRIMARY KEY,
                attempts INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS recovery_exhausted (
                action TEXT PRIMARY KEY
            );
            CREATE TABLE IF NOT EXISTS recovery_attempts (
                id INTEGER PRIMARY KEY,
                action TEXT NOT NULL,
                fault TEXT NOT NULL,
                at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS recovery_attempt_lookup
                ON recovery_attempts(action, at);
            CREATE TABLE IF NOT EXISTS recovery_events (
                id INTEGER PRIMARY KEY,
                action TEXT NOT NULL,
                fault TEXT NOT NULL,
                allowed INTEGER NOT NULL,
                reason TEXT NOT NULL,
                at REAL
            );
            """
        )

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            if self._closed:
                raise sqlite3.ProgrammingError("recovery store is closed")
            self._db.execute("BEGIN IMMEDIATE")
            try:
                yield self._db
            except BaseException:
                self._db.rollback()
                raise
            else:
                self._db.commit()

    @staticmethod
    def _valid_label(value: object) -> bool:
        # Labels are compatibility inputs only; do not store arbitrary caller text.
        return value is None or (
            isinstance(value, str)
            and 0 < len(value) <= 128
            and value.isascii()
            and all(char.isalnum() or char in "-_:." for char in value)
        )

    def _now(self) -> float | None:
        try:
            value = self._clock()
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return None
            value = float(value)
            return value if math.isfinite(value) and value >= 0 else None
        except (Exception, OverflowError):
            return None

    @staticmethod
    def _active_latch(db: sqlite3.Connection) -> str | None:
        active = {row[0] for row in db.execute("SELECT fault FROM recovery_latches")}
        return next((fault for fault in LATCH_PRIORITY if fault in active), None)

    @staticmethod
    def _event(
        db: sqlite3.Connection,
        action: str,
        fault: str,
        decision: RecoveryDecision,
        at: float | None = None,
    ) -> RecoveryDecision:
        db.execute(
            "INSERT INTO recovery_events(action, fault, allowed, reason, at) "
            "VALUES (?, ?, ?, ?, ?)",
            (action, fault, int(decision.allowed), decision.reason, at),
        )
        db.execute(
            "DELETE FROM recovery_events WHERE id NOT IN "
            "(SELECT id FROM recovery_events ORDER BY id DESC LIMIT ?)",
            (_MAX_EVENTS,),
        )
        return decision

    def allow(
        self,
        action: str,
        *,
        fault: str = "transport",
        incident_id: str | None = None,
        session_id: str | None = None,
        adapter_idle: bool = False,
        adapter_owned: bool = False,
    ) -> RecoveryDecision:
        """Atomically decide and reserve an attempt; fail closed on invalid inputs.

        Independent stop/output invalidation returns before reading SQLite, the
        clock, labels, or fault context. These decisions grant no recovery, motor
        enable or playback capability. Caller-provided labels are ignored after
        validation and cannot identify a new budget bucket.
        """
        if isinstance(action, str) and action in INDEPENDENT_ACTIONS:
            return RecoveryDecision(True, "independent_stop")
        if not isinstance(action, str) or action not in POLICIES:
            return RecoveryDecision(False, "unknown_action")
        if not isinstance(fault, str) or fault not in KNOWN_FAULTS:
            return RecoveryDecision(False, "unknown_fault")
        if not self._valid_label(incident_id) or not self._valid_label(session_id):
            return RecoveryDecision(False, "invalid_input")
        if type(adapter_idle) is not bool or type(adapter_owned) is not bool:
            return RecoveryDecision(False, "invalid_input")
        try:
            with self._transaction() as db:
                if fault in LATCH_PRIORITY:
                    db.execute("INSERT OR IGNORE INTO recovery_latches(fault) VALUES (?)", (fault,))
                active = self._active_latch(db)
                if active:
                    return self._event(
                        db, action, fault, RecoveryDecision(False, f"latch_{active}")
                    )
                exhausted = db.execute("SELECT action FROM recovery_exhausted LIMIT 1").fetchone()
                if exhausted:
                    return self._event(
                        db, action, fault, RecoveryDecision(False, "budget_exhausted")
                    )
                if fault == "child_stop" or (
                    fault == "none" and action in {"transport_reconnect", "adapter_restart"}
                ):
                    return self._event(
                        db, action, fault, RecoveryDecision(False, "fault_not_recoverable")
                    )
                if action == "adapter_restart":
                    if not adapter_owned:
                        return self._event(
                            db, action, fault, RecoveryDecision(False, "adapter_not_owned")
                        )
                    if not adapter_idle:
                        return self._event(
                            db, action, fault, RecoveryDecision(False, "adapter_not_idle")
                        )
                now = self._now()
                if now is None:
                    return self._event(db, action, fault, RecoveryDecision(False, "invalid_clock"))
                row = db.execute(
                    "SELECT value FROM recovery_meta WHERE key = 'last_clock'"
                ).fetchone()
                if row is not None and now < row[0]:
                    return self._event(
                        db,
                        action,
                        fault,
                        RecoveryDecision(False, "clock_rollback", row[0] - now),
                    )
                db.execute(
                    "INSERT INTO recovery_meta(key, value) VALUES ('last_clock', ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (now,),
                )
                # Keep all grants needed by any active window, including global restarts.
                db.execute(
                    "DELETE FROM recovery_attempts WHERE at <= ?",
                    (now - GLOBAL_ADAPTER_RESTART_WINDOW_SECONDS,),
                )
                policy = POLICIES[action]
                used = db.execute(
                    "SELECT attempts FROM recovery_budgets WHERE action = ?", (action,)
                ).fetchone()
                if used and used[0] >= policy.max_attempts:
                    db.execute("INSERT OR IGNORE INTO recovery_exhausted VALUES (?)", (action,))
                    return self._event(
                        db, action, fault, RecoveryDecision(False, "incident_attempt_limit"), now
                    )
                recent = db.execute(
                    "SELECT fault, at FROM recovery_attempts "
                    "WHERE action = ? AND at > ? ORDER BY at",
                    (action, now - policy.window_seconds),
                ).fetchall()
                if recent and now - recent[-1][1] < policy.cooldown_seconds:
                    return self._event(
                        db,
                        action,
                        fault,
                        RecoveryDecision(
                            False, "cooldown", policy.cooldown_seconds - (now - recent[-1][1])
                        ),
                        now,
                    )
                if len(recent) >= policy.max_attempts:
                    db.execute("INSERT OR IGNORE INTO recovery_exhausted VALUES (?)", (action,))
                    return self._event(
                        db,
                        action,
                        fault,
                        RecoveryDecision(
                            False,
                            "action_attempt_limit",
                            recent[0][1] + policy.window_seconds - now,
                        ),
                        now,
                    )
                if action == "adapter_restart":
                    global_attempts = db.execute(
                        "SELECT at FROM recovery_attempts WHERE action = 'adapter_restart' "
                        "AND at > ? ORDER BY at",
                        (now - GLOBAL_ADAPTER_RESTART_WINDOW_SECONDS,),
                    ).fetchall()
                    if len(global_attempts) >= GLOBAL_ADAPTER_RESTART_LIMIT:
                        db.execute("INSERT OR IGNORE INTO recovery_exhausted VALUES (?)", (action,))
                        return self._event(
                            db,
                            action,
                            fault,
                            RecoveryDecision(
                                False,
                                "global_adapter_restart_limit",
                                global_attempts[0][0] + GLOBAL_ADAPTER_RESTART_WINDOW_SECONDS - now,
                            ),
                            now,
                        )
                db.execute(
                    "INSERT INTO recovery_attempts(action, fault, at) VALUES (?, ?, ?)",
                    (action, fault, now),
                )
                db.execute(
                    "INSERT INTO recovery_budgets(action, attempts) VALUES (?, 1) "
                    "ON CONFLICT(action) DO UPDATE SET attempts = attempts + 1",
                    (action,),
                )
                return self._event(db, action, fault, RecoveryDecision(True, "reserved"), now)
        except sqlite3.Error:
            return RecoveryDecision(False, "store_unavailable")

    # There is intentionally no dry-run allowance which could bypass reservation.
    decide = allow
    record = allow

    def latch(self, fault: str) -> RecoveryDecision:
        """Persist a known veto without relying on a working clock."""
        if not isinstance(fault, str) or fault not in LATCH_PRIORITY:
            return RecoveryDecision(False, "unknown_latch")
        try:
            with self._transaction() as db:
                db.execute("INSERT OR IGNORE INTO recovery_latches(fault) VALUES (?)", (fault,))
                return self._event(db, "latch", fault, RecoveryDecision(False, f"latch_{fault}"))
        except sqlite3.Error:
            return RecoveryDecision(False, "store_unavailable")

    def clear_latch(self, fault: str, *, authorized: bool = False) -> RecoveryDecision:
        """Consume a trusted parent's authorization result; authenticate upstream.

        Clearing a veto does not replenish attempts or reset the persisted clock.
        Truthy strings/integers do not satisfy the explicit authorization flag.
        """
        if authorized is not True:
            return RecoveryDecision(False, "parent_authorization_required")
        if not isinstance(fault, str) or fault not in LATCH_PRIORITY:
            return RecoveryDecision(False, "unknown_latch")
        try:
            with self._transaction() as db:
                db.execute("DELETE FROM recovery_latches WHERE fault = ?", (fault,))
                return self._event(
                    db, "clear_latch", fault, RecoveryDecision(True, "latch_cleared")
                )
        except sqlite3.Error:
            return RecoveryDecision(False, "store_unavailable")

    def reset_budget(
        self, action: str, *, authorized: bool = False, postcondition_verified: bool = False
    ) -> RecoveryDecision:
        """Start a new incident only after trusted adult and recovery verification.

        These flags consume upstream decisions; they are not authentication or
        evidence themselves. Global rate history, clock and physical latches stay.
        """
        if authorized is not True or postcondition_verified is not True:
            return RecoveryDecision(False, "verified_parent_recovery_required")
        if not isinstance(action, str) or action not in POLICIES:
            return RecoveryDecision(False, "unknown_action")
        try:
            with self._transaction() as db:
                db.execute("DELETE FROM recovery_budgets WHERE action = ?", (action,))
                db.execute("DELETE FROM recovery_exhausted WHERE action = ?", (action,))
                return RecoveryDecision(True, "budget_reset_after_verified_recovery")
        except sqlite3.Error:
            return RecoveryDecision(False, "store_unavailable")

    def latches(self) -> tuple[str, ...]:
        """Read persisted vetoes; storage failure raises rather than implying none."""
        with self._lock:
            if self._closed:
                raise sqlite3.ProgrammingError("recovery store is closed")
            present = {row[0] for row in self._db.execute("SELECT fault FROM recovery_latches")}
            return tuple(fault for fault in LATCH_PRIORITY if fault in present)

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._db.close()
                self._closed = True

    def __enter__(self) -> RecoveryController:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

"""Curated activity state and generation-based cancellation. No speech/model calls."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True)
class Activity:
    id: str
    title_de: str
    prompts_de: tuple[str, ...]
    concept_ids: tuple[str, ...]
    parent_reviewed: bool


def load_catalog(path: str | Path) -> dict[str, Activity]:
    data = json.loads(Path(path).read_text())
    if set(data) != {"schema_version", "language", "activities"}:
        raise ValueError("unknown or missing catalog field")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ValueError("unsupported catalog schema")
    if data["language"] != "de-DE" or not isinstance(data["activities"], list):
        raise ValueError("catalog must contain German activities")
    result = {}
    for row in data["activities"]:
        if not isinstance(row, dict) or set(row) != {
            "id",
            "title_de",
            "prompts_de",
            "concept_ids",
            "parent_reviewed",
            "source",
        }:
            raise ValueError("invalid activity fields")
        if not isinstance(row["id"], str) or not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", row["id"]):
            raise ValueError("invalid activity ID")
        if row["id"] in result or type(row["parent_reviewed"]) is not bool:
            raise ValueError("duplicate activity or invalid parent review flag")
        for key in ("title_de", "source"):
            if not isinstance(row[key], str) or not 1 <= len(row[key]) <= 240:
                raise ValueError("invalid activity text")
        prompts, concepts = row["prompts_de"], row["concept_ids"]
        if not isinstance(prompts, list) or not 1 <= len(prompts) <= 12:
            raise ValueError("activity requires bounded prompts")
        if any(not isinstance(s, str) or not 1 <= len(s) <= 400 for s in prompts):
            raise ValueError("invalid prompt")
        if (
            not isinstance(concepts, list)
            or not concepts
            or any(
                not isinstance(s, str) or not re.fullmatch(r"[a-z0-9_.-]{1,80}", s)
                for s in concepts
            )
        ):
            raise ValueError("invalid concept IDs")
        result[row["id"]] = Activity(
            row["id"], row["title_de"], tuple(prompts), tuple(concepts), row["parent_reviewed"]
        )
    return result


@dataclass(frozen=True)
class SpeechTurn:
    session_id: str
    generation: int
    text_de: str


class ActivitySession:
    """A demonstration loop, not parent authentication or a child-ready runtime."""

    def __init__(self, activity: Activity, *, simulation: bool = False):
        if type(simulation) is not bool:
            raise ValueError("simulation must be an explicit boolean")
        if not simulation and not activity.parent_reviewed:
            raise PermissionError("activity has not received parent content review")
        self.activity = activity
        self.session_id = str(uuid4())
        self.generation = 0
        self.position = 0
        self.stopped = False

    def next_prompt(self) -> SpeechTurn | None:
        if self.stopped or self.position == len(self.activity.prompts_de):
            return None
        turn = SpeechTurn(self.session_id, self.generation, self.activity.prompts_de[self.position])
        self.position += 1
        return turn

    def stop(self) -> None:
        self.generation += 1
        self.stopped = True

    def accepts(self, turn: SpeechTurn) -> bool:
        return (
            not self.stopped
            and turn.session_id == self.session_id
            and turn.generation == self.generation
        )

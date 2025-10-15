"""Quiz generation and scoring helpers."""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

from .parsing import CarRecord


@dataclass(frozen=True)
class QuizChoice:
    id: str
    label: str
    record: CarRecord


@dataclass(frozen=True)
class QuizQuestion:
    id: str
    image_record: CarRecord
    correct_choice_id: str
    choices: Sequence[QuizChoice]


def generate_question(
    records: Sequence[CarRecord],
    *,
    num_choices: int,
    rng: random.Random,
) -> QuizQuestion:
    if num_choices < 2:
        raise ValueError("Need at least 2 choices for a quiz question.")

    catalog = _group_by_meta(records)
    unique_keys = list(catalog.keys())
    if len(unique_keys) < num_choices:
        raise ValueError(
            f"Not enough unique car combinations to generate {num_choices} choices "
            f"(only {len(unique_keys)} available).",
        )

    target_key = rng.choice(unique_keys)
    target_records = catalog[target_key]
    image_record = rng.choice(target_records)

    distractor_keys = _pick_distractor_keys(
        catalog=catalog,
        target_key=target_key,
        num_needed=num_choices - 1,
        rng=rng,
    )

    choices: List[QuizChoice] = []
    correct_choice_id = str(uuid.uuid4())
    choices.append(
        QuizChoice(
            id=correct_choice_id,
            label=_format_label(*target_key),
            record=image_record,
        ),
    )

    for key in distractor_keys:
        record = catalog[key][0]
        choices.append(
            QuizChoice(
                id=str(uuid.uuid4()),
                label=_format_label(*key),
                record=record,
            ),
        )

    rng.shuffle(choices)
    return QuizQuestion(
        id=str(uuid.uuid4()),
        image_record=image_record,
        correct_choice_id=correct_choice_id,
        choices=choices,
    )


def is_correct(question: QuizQuestion, choice_id: str) -> bool:
    return question.correct_choice_id == choice_id


def _group_by_meta(records: Sequence[CarRecord]) -> Dict[Tuple[str, str, int], List[CarRecord]]:
    grouped: Dict[Tuple[str, str, int], List[CarRecord]] = {}
    for record in records:
        key = (record.make, record.model, record.year)
        grouped.setdefault(key, []).append(record)
    return grouped


def _pick_distractor_keys(
    *,
    catalog: Dict[Tuple[str, str, int], List[CarRecord]],
    target_key: Tuple[str, str, int],
    num_needed: int,
    rng: random.Random,
) -> List[Tuple[str, str, int]]:
    make, _, year = target_key
    same_make = [key for key in catalog.keys() if key[0] == make and key != target_key]
    other = [key for key in catalog.keys() if key[0] != make]

    rng.shuffle(same_make)
    rng.shuffle(other)

    selected: List[Tuple[str, str, int]] = []

    # Prioritise similar makes/models
    for key in same_make:
        selected.append(key)
        if len(selected) >= num_needed:
            break

    if len(selected) < num_needed:
        # Try to include close years first
        other_sorted = sorted(
            other,
            key=lambda candidate: abs(candidate[2] - year),
        )
        for key in other_sorted:
            if key not in selected:
                selected.append(key)
            if len(selected) >= num_needed:
                break

    if len(selected) < num_needed:
        # Fallback to any remaining entries
        pool = [key for key in catalog.keys() if key != target_key and key not in selected]
        rng.shuffle(pool)
        for key in pool:
            selected.append(key)
            if len(selected) >= num_needed:
                break

    return selected[:num_needed]


def _format_label(make: str, model: str, year: int) -> str:
    return f"{make} {model} {year}"


"""Session state helpers for the Streamlit app."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import streamlit as st

from .quiz import QuizChoice, QuizQuestion


@dataclass
class HistoryEntry:
    question_id: str
    selected_label: str
    correct_label: str
    correct: bool


def init_game_state() -> None:
    session = st.session_state
    session.setdefault("score", 0)
    session.setdefault("rounds_played", 0)
    session.setdefault("history", [])
    session.setdefault("current_question", None)
    session.setdefault("answered", False)
    session.setdefault("selected_choice_id", None)
    if "rng" not in session:
        seed = random.randint(0, 1_000_000)
        session["rng_seed"] = seed
        session["rng"] = random.Random(seed)


def get_rng() -> random.Random:
    rng = st.session_state.get("rng")
    if rng is None:
        rng = random.Random()
        st.session_state["rng"] = rng
    return rng


def persist_question(question: QuizQuestion) -> None:
    st.session_state["current_question"] = question
    st.session_state["answered"] = False
    st.session_state["selected_choice_id"] = None


def register_answer(choice_id: str, *, correct: bool, question: QuizQuestion, choice: QuizChoice) -> None:
    st.session_state["answered"] = True
    st.session_state["rounds_played"] += 1
    if correct:
        st.session_state["score"] += 1

    history: List[HistoryEntry] = st.session_state.get("history", [])
    history.append(
        HistoryEntry(
            question_id=question.id,
            selected_label=choice.label,
            correct_label=_get_correct_choice(question).label,
            correct=correct,
        ),
    )
    st.session_state["history"] = history[-25:]  # keep recent entries


def set_selected_choice(choice_id: Optional[str]) -> None:
    st.session_state["selected_choice_id"] = choice_id


def get_selected_choice_id() -> Optional[str]:
    return st.session_state.get("selected_choice_id")


def get_current_question() -> Optional[QuizQuestion]:
    return st.session_state.get("current_question")


def has_answered() -> bool:
    return bool(st.session_state.get("answered"))


def _get_correct_choice(question: QuizQuestion) -> QuizChoice:
    for choice in question.choices:
        if choice.id == question.correct_choice_id:
            return choice
    raise ValueError("Correct choice not found on the question.")
